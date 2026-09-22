// pybersdev-golden-confirm
//
// The background app that holds Accessibility and Screen Recording for
// scripts/golden-confirm.py, so that Terminal holds neither (PYB-94 AC 11). macOS
// judges a program Terminal starts directly by Terminal's grants, so this is an app
// started with `open`, reading one request file and writing one result file.
//
// It performs only the operations named in `HelperOperation` and never runs a script
// or command it is given (PYB-94 AC 15). Every AppleScript it sends is written here,
// and the only values a request places into one are paths and cell names it escapes.
//
// UPDATES
// 2026-09-22  Reads a table's size and cell names, and names a closed Numbers, for PYB-111.
// 2026-09-17  Written for PYB-94.

import AppKit
import ApplicationServices
import CoreGraphics
import Foundation
import ImageIO
import ScreenCaptureKit
import UniformTypeIdentifiers

let numbersBundleIdentifier = "com.apple.Numbers"
let appleScriptTimeoutSeconds = 60
let windowAttempts = 20
let otherDesktopAttempts = 3
let connectionInvalidError = -609
// What Automation's permission check answers for an app that is not running.
let processNotFoundError: OSStatus = -600
let quitTimeoutSeconds = 10
let retryPauseSeconds = 0.5
// The Numbers this run launched, which the deadline force-quits because nothing else will.
nonisolated(unsafe) var numbersLaunchedByRun: NSRunningApplication?
// The four-character code AppleScript uses for missing value, which Swift does not import.
let missingValueCode: OSType = 0x6D73_6E67

// MARK: Request and result

enum HelperOperation: String, Codable {
    case permissionsCheck
    case documentInspect
}

struct CellAddress: Codable {
    let sheet: String
    let table: String
    let cell: String
}

struct TableAddress: Codable {
    let sheet: String
    let table: String
}

struct HelperRequest: Codable {
    let operation: HelperOperation
    let resultPath: String
    let deadlineSeconds: Double
    var documentPath: String?
    var savedCopyPath: String?
    var captureDirectory: String?
    var cells: [CellAddress]?
    var tables: [TableAddress]?
    var maxCaptures: Int?
    var freshNumbers: Bool?
}

struct HelperProblem: Codable {
    let kind: String
    let detail: String
    let remedy: String
}

struct CellValue: Codable {
    let kind: String
    let text: String
}

struct InspectorElement: Codable {
    let role: String
    let title: String
    let label: String
    let value: String
}

struct CellReading: Codable {
    let address: CellAddress
    var formattedValue: String?
    var formula: String?
    var formatKind: String?
    var value: CellValue?
    var dataFormat: [InspectorElement] = []
    var inspectorCapture: String?
}

// A covered cell answers with its anchor's name, which is how the script finds merges.
struct TableReading: Codable {
    let address: TableAddress
    let rowCount: Int
    let columnCount: Int
    let cellNames: [[String]]
}

struct SheetCapture: Codable {
    let sheet: String
    let path: String
}

struct HelperResult: Codable {
    let sourceHash: String
    let operation: String
    var problems: [HelperProblem] = []
    var numbersVersion: String?
    var launchedNumbers: Bool?
    var openOutcome: String?
    var alertText: [String] = []
    var cells: [CellReading] = []
    var tables: [TableReading] = []
    var sheetCaptures: [SheetCapture] = []
    var savedCopy: Bool?
}

struct HelperFailure: Error {
    let problem: HelperProblem
}

// Local time, so a log line matches the clock the developer was watching.
let logTimeFormatter: DateFormatter = {
    let formatter = DateFormatter()
    formatter.locale = Locale(identifier: "en_US_POSIX")
    formatter.dateFormat = "yyyy-MM-dd HH:mm:ss"
    return formatter
}()

func writeLog(_ message: String) {
    FileHandle.standardError.write(Data("\(logTimeFormatter.string(from: Date())) \(message)\n".utf8))
}

func readSourceHash() -> String {
    Bundle.main.object(forInfoDictionaryKey: "PybersSourceHash") as? String ?? ""
}

func writeResult(_ result: HelperResult, to path: String) {
    let encoder = JSONEncoder()
    encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
    // A result that cannot be written leaves the script with no result file, which it reports.
    guard let data = try? encoder.encode(result) else { return }
    try? data.write(to: URL(fileURLWithPath: path), options: .atomic)
}

// MARK: Session and permissions

func findSessionProblems() -> [HelperProblem] {
    let session = CGSessionCopyCurrentDictionary() as? [String: Any] ?? [:]
    var problems: [HelperProblem] = []
    if session[kCGSessionOnConsoleKey as String] as? Bool != true {
        problems.append(HelperProblem(
            kind: "session",
            detail: "no logged-in desktop session is on the console",
            remedy: "log in at the Mac itself, not only over SSH"))
    }
    if session["CGSSessionScreenIsLocked"] as? Bool == true {
        problems.append(HelperProblem(
            kind: "session",
            detail: "the screen is locked",
            remedy: "unlock the Mac before running"))
    }
    return problems
}

func findGrantProblems() -> [HelperProblem] {
    var problems: [HelperProblem] = []
    if !AXIsProcessTrusted() {
        problems.append(HelperProblem(
            kind: "accessibility",
            detail: "pybersdev-golden-confirm does not hold Accessibility",
            remedy: "System Settings, Privacy & Security, Accessibility: add and enable "
                + Bundle.main.bundlePath))
    }
    if !CGPreflightScreenCaptureAccess() {
        problems.append(HelperProblem(
            kind: "screenRecording",
            detail: "pybersdev-golden-confirm does not hold Screen Recording",
            remedy: "System Settings, Privacy & Security, Screen & System Audio Recording: "
                + "add and enable " + Bundle.main.bundlePath))
    }
    return problems
}

func findAutomationProblem() -> HelperProblem? {
    let target = NSAppleEventDescriptor(bundleIdentifier: numbersBundleIdentifier)
    // Asking is the only way macOS offers to grant Automation; Settings cannot add it.
    let status = AEDeterminePermissionToAutomateTarget(
        target.aeDesc, typeWildCard, typeWildCard, true)
    switch status {
    case noErr:
        return nil
    case processNotFoundError:
        return HelperProblem(
            kind: "numbersNotRunning",
            detail: "Numbers is not running, so whether the helper may control it is unknown",
            remedy: "open Numbers, then rerun")
    default:
        return HelperProblem(
            kind: "automation",
            detail: "pybersdev-golden-confirm may not control Numbers (status \(status))",
            remedy: "System Settings, Privacy & Security, Automation: enable Numbers "
                + "under pybersdev-golden-confirm")
    }
}

func checkAutomationPermission() throws {
    if let problem = findAutomationProblem() { throw HelperFailure(problem: problem) }
}

// A damaged golden can crash Numbers, which would take unsaved work in other documents with it.
func checkNoUnsavedDocuments(timeoutSeconds: Int = appleScriptTimeoutSeconds) throws {
    let names = try runAppleScript(
        "set unsaved to {}\n"
            + "repeat with d in documents\n"
            + "if modified of d then set end of unsaved to name of d\n"
            + "end repeat\n"
            + "return unsaved",
        timeoutSeconds: timeoutSeconds)
    guard names.numberOfItems == 0 else {
        let listed = (1...names.numberOfItems).compactMap { names.atIndex($0)?.stringValue }
        throw HelperFailure(problem: HelperProblem(
            kind: "unsavedDocuments",
            detail: "Numbers holds unsaved changes in " + listed.joined(separator: ", "),
            remedy: "save or close those documents in Numbers, then rerun"))
    }
}

// MARK: Request validation

func resolvePath(_ path: String) -> String {
    URL(fileURLWithPath: path).resolvingSymlinksInPath().path
}

func checkTemporaryPath(_ path: String?, field: String) throws -> String {
    let temporary = resolvePath(NSTemporaryDirectory()) + "/"
    guard let path, path.hasSuffix(".numbers"), !path.contains("/../"),
          (resolvePath((path as NSString).deletingLastPathComponent) + "/").hasPrefix(temporary)
    else {
        throw HelperFailure(problem: HelperProblem(
            kind: "request",
            detail: "\(field) must be a .numbers path inside \(temporary)",
            remedy: "run the helper only through scripts/golden-confirm.py"))
    }
    return path
}

func checkCaptureDirectory(_ path: String?) throws -> String {
    var isDirectory: ObjCBool = false
    // Resolved first, so `..` cannot walk a capture out of the report folder.
    guard let path, resolvePath(path).contains("/workarea/golden-confirm/"),
          !path.split(separator: "/").contains(".."),
          FileManager.default.fileExists(atPath: path, isDirectory: &isDirectory),
          isDirectory.boolValue
    else {
        throw HelperFailure(problem: HelperProblem(
            kind: "request",
            detail: "captureDirectory must be an existing folder under workarea/golden-confirm/",
            remedy: "run the helper only through scripts/golden-confirm.py"))
    }
    return path
}

// MARK: AppleScript

func quoteAppleScript(_ text: String) -> String {
    "\"" + text.replacingOccurrences(of: "\\", with: "\\\\")
        .replacingOccurrences(of: "\"", with: "\\\"") + "\""
}

struct AppleScriptError: Error {
    let number: Int
    let message: String
}

func runAppleScript(
    _ body: String, timeoutSeconds: Int = appleScriptTimeoutSeconds
) throws -> NSAppleEventDescriptor {
    let source = """
        with timeout of \(timeoutSeconds) seconds
        tell application id "\(numbersBundleIdentifier)"
        \(body)
        end tell
        end timeout
        """
    guard let script = NSAppleScript(source: source) else {
        throw AppleScriptError(number: 0, message: "the helper wrote an AppleScript that does not compile")
    }
    var error: NSDictionary?
    let descriptor = script.executeAndReturnError(&error)
    if let error {
        throw AppleScriptError(
            number: error[NSAppleScript.errorNumber] as? Int ?? 0,
            message: error[NSAppleScript.errorMessage] as? String ?? "unknown")
    }
    return descriptor
}

func isMissingValue(_ descriptor: NSAppleEventDescriptor) -> Bool {
    descriptor.descriptorType == typeType && descriptor.typeCodeValue == missingValueCode
}

func readOptionalText(_ descriptor: NSAppleEventDescriptor) -> String? {
    isMissingValue(descriptor) ? nil : descriptor.stringValue
}

func readCellValue(_ descriptor: NSAppleEventDescriptor) -> CellValue {
    if isMissingValue(descriptor) {
        return CellValue(kind: "empty", text: "")
    }
    switch descriptor.descriptorType {
    case typeTrue, typeFalse, typeBoolean:
        return CellValue(kind: "boolean", text: descriptor.booleanValue ? "true" : "false")
    case typeIEEE64BitFloatingPoint, typeIEEE32BitFloatingPoint, typeSInt32, typeSInt16, typeSInt64:
        return CellValue(kind: "number", text: String(descriptor.doubleValue))
    case typeLongDateTime:
        // A fixed calendar and locale, so the text reads the same on every developer's Mac.
        let formatter = DateFormatter()
        formatter.calendar = Calendar(identifier: .gregorian)
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
        return CellValue(kind: "date", text: descriptor.dateValue.map(formatter.string) ?? "")
    default:
        return CellValue(kind: "text", text: descriptor.stringValue ?? "")
    }
}

func formatCellReference(_ address: CellAddress, documentId: String) -> String {
    "cell \(quoteAppleScript(address.cell)) of table \(quoteAppleScript(address.table)) "
        + "of sheet \(quoteAppleScript(address.sheet)) "
        + "of document id \(quoteAppleScript(documentId))"
}

// MARK: Accessibility

func readAttribute(_ element: AXUIElement, _ attribute: String) -> AnyObject? {
    var value: AnyObject?
    let status = AXUIElementCopyAttributeValue(element, attribute as CFString, &value)
    return status == .success ? value : nil
}

func readText(_ element: AXUIElement, _ attribute: String) -> String {
    switch readAttribute(element, attribute) {
    case let text as String: return text
    case let number as NSNumber: return number.stringValue
    default: return ""
    }
}

func collectElements(_ root: AXUIElement) -> [AXUIElement] {
    var ordered: [AXUIElement] = [root]
    for child in readAttribute(root, kAXChildrenAttribute) as? [AXUIElement] ?? [] {
        ordered.append(contentsOf: collectElements(child))
    }
    return ordered
}

func findNumbersWindow(named title: String, pid: pid_t) -> AXUIElement? {
    let application = AXUIElementCreateApplication(pid)
    let windows = readAttribute(application, kAXWindowsAttribute) as? [AXUIElement] ?? []
    // The title bar may drop the extension that AppleScript's window name keeps.
    let stem = (title as NSString).deletingPathExtension
    let matching = windows.filter { [title, stem].contains(readText($0, kAXTitleAttribute)) }
    if matching.isEmpty {
        var raw: AnyObject?
        let status = AXUIElementCopyAttributeValue(application, kAXWindowsAttribute as CFString, &raw)
        writeLog("no Accessibility window titled '\(title)' among "
            + windows.map { "'\(readText($0, kAXTitleAttribute))'" }.joined(separator: ", ")
            + " (AXWindows status \(status.rawValue), trusted \(AXIsProcessTrusted()), "
            + describeWindowPlacement(pid: pid) + ")")
    }
    // Numbers keeps a second, empty window under the same title, so the fuller one is the document.
    return matching.max { collectElements($0).count < collectElements($1).count }
}

func countNumbersWindows(pid: pid_t) -> (all: Int, onScreen: Int) {
    let listed = CGWindowListCopyWindowInfo([.optionAll], kCGNullWindowID) as? [[String: Any]] ?? []
    let owned = listed.filter {
        ($0[kCGWindowOwnerPID as String] as? Int32) == pid
            && ($0[kCGWindowLayer as String] as? Int) == 0
    }
    return (owned.count, owned.filter { ($0[kCGWindowIsOnscreen as String] as? Bool) == true }.count)
}

// Accessibility lists only the windows on the current desktop, so a miss says where they are.
func describeWindowPlacement(pid: pid_t) -> String {
    let counts = countNumbersWindows(pid: pid)
    let front = NSWorkspace.shared.frontmostApplication?.localizedName ?? "unknown"
    return "Numbers windows \(counts.all), on screen \(counts.onScreen), frontmost app \(front)"
}

// Refused rather than brought forward, so nothing the developer types can land in the copy.
func checkNumbersOnThisDesktop(pid: pid_t) throws {
    let counts = countNumbersWindows(pid: pid)
    guard counts.all > 0, counts.onScreen == 0 else { return }
    throw HelperFailure(problem: HelperProblem(
        kind: "otherDesktop",
        detail: "Numbers opened its window on another desktop, where the helper cannot reach it",
        remedy: "leave any full-screen app and stay on a regular desktop during the run, then rerun"))
}

func findButton(in root: AXUIElement, role: String, description: String) -> AXUIElement? {
    collectElements(root).first {
        readText($0, kAXRoleAttribute) == role
            && readText($0, kAXDescriptionAttribute) == description
    }
}

func readNumbersWindows(pid: pid_t) -> [AXUIElement] {
    readAttribute(AXUIElementCreateApplication(pid), kAXWindowsAttribute) as? [AXUIElement] ?? []
}

// Only windows that appeared after opening are searched, so a developer's own document is never
// read as an alert or has a button pressed in it.
func findAlerts(pid: pid_t, excluding existing: [AXUIElement]) -> [AXUIElement] {
    var alerts: [AXUIElement] = []
    for window in readNumbersWindows(pid: pid) where !existing.contains(where: { CFEqual($0, window) }) {
        let subrole = readText(window, kAXSubroleAttribute)
        // A document window can report a dialog subrole while hidden or minimized; an alert has no document.
        let isDocument = !readText(window, kAXDocumentAttribute).isEmpty
            || collectElements(window).contains { readText($0, kAXRoleAttribute) == kAXToolbarRole }
        writeLog("new window '\(readText(window, kAXTitleAttribute))': role \(readText(window, kAXRoleAttribute)), "
            + "subrole \(subrole), document \(isDocument), "
            + "hidden \(NSRunningApplication(processIdentifier: pid)?.isHidden ?? false)")
        if !isDocument, subrole == kAXDialogSubrole || subrole == kAXSystemDialogSubrole {
            alerts.append(window)
        }
        alerts += (readAttribute(window, kAXChildrenAttribute) as? [AXUIElement] ?? [])
            .filter { readText($0, kAXRoleAttribute) == kAXSheetRole }
    }
    return alerts
}

func readAlertText(_ alerts: [AXUIElement]) -> [String] {
    alerts.flatMap { alert in
        collectElements(alert)
            .filter { readText($0, kAXRoleAttribute) == kAXStaticTextRole }
            .map { readText($0, kAXValueAttribute) }
            .filter { !$0.isEmpty }
    }
}

func openCellTab(in window: AXUIElement) throws {
    if findButton(in: window, role: kAXRadioButtonRole, description: "Cell") == nil,
       let format = findButton(in: window, role: kAXRadioButtonRole, description: "Format") {
        AXUIElementPerformAction(format, kAXPressAction as CFString)
        Thread.sleep(forTimeInterval: 0.5)
    }
    guard let cellTab = findButton(in: window, role: kAXRadioButtonRole, description: "Cell") else {
        // A screen that locks mid-run hides the inspector too, and says more than a language guess.
        if let locked = findSessionProblems().first { throw HelperFailure(problem: locked) }
        throw HelperFailure(problem: HelperProblem(
            kind: "language",
            detail: "the inspector's Cell tab was not found, so Numbers may run in a language "
                + "other than English",
            remedy: "set Numbers to English in System Settings, General, Language & Region, "
                + "Applications, then rerun"))
    }
    AXUIElementPerformAction(cellTab, kAXPressAction as CFString)
    Thread.sleep(forTimeInterval: 0.5)
}

func readDataFormat(in window: AXUIElement) throws -> [InspectorElement] {
    let elements = collectElements(window)
    // The format-kind popup sits before its own "Data Format" heading, so the walk starts at the tabs.
    guard let start = elements.firstIndex(where: {
        readText($0, kAXRoleAttribute) == kAXRadioButtonRole
            && readText($0, kAXDescriptionAttribute) == "Arrange"
    }), elements[start...].contains(where: {
        readText($0, kAXRoleAttribute) == kAXStaticTextRole
            && readText($0, kAXValueAttribute) == "Data Format"
    }) else {
        throw HelperFailure(problem: HelperProblem(
            kind: "language",
            detail: "the Cell tab shows no Data Format section",
            remedy: "set Numbers to English, then rerun"))
    }
    var section: [InspectorElement] = []
    for element in elements[(start + 1)...] {
        let role = readText(element, kAXRoleAttribute)
        if role == kAXDisclosureTriangleRole { break }
        if role == kAXStaticTextRole, ["Fill", "Border"].contains(readText(element, kAXValueAttribute)) {
            break
        }
        guard [kAXStaticTextRole, kAXTextFieldRole, kAXPopUpButtonRole, kAXCheckBoxRole,
               kAXRadioButtonRole].contains(role) else { continue }
        section.append(InspectorElement(
            role: role,
            title: readText(element, kAXTitleAttribute),
            label: readText(element, kAXDescriptionAttribute),
            value: readText(element, kAXValueAttribute)))
    }
    return section
}

// MARK: Capture

func readFrame(_ element: AXUIElement) -> CGRect? {
    guard let position = readAttribute(element, kAXPositionAttribute),
          let size = readAttribute(element, kAXSizeAttribute)
    else { return nil }
    var origin = CGPoint.zero
    var extent = CGSize.zero
    // Both attributes are AXValue by the Accessibility contract, so the casts cannot fail.
    AXValueGetValue(position as! AXValue, .cgPoint, &origin)
    AXValueGetValue(size as! AXValue, .cgSize, &extent)
    return CGRect(origin: origin, size: extent)
}

// Captured at the display's own pixels and kept lossless, so graphical detail stays sharp.
// ScreenCaptureKit captures one window whether it is hidden or covered, which `screencapture -l` cannot.
func captureWindowImage(id windowId: Int) -> (CGImage?, String) {
    var image: CGImage?
    var said = ""
    let done = DispatchSemaphore(value: 0)
    SCShareableContent.getExcludingDesktopWindows(true, onScreenWindowsOnly: false) { content, error in
        guard let window = content?.windows.first(where: { Int($0.windowID) == windowId }) else {
            said = error.map { "\($0)" } ?? "ScreenCaptureKit lists no window \(windowId)"
            done.signal()
            return
        }
        let filter = SCContentFilter(desktopIndependentWindow: window)
        let configuration = SCStreamConfiguration()
        configuration.width = Int(filter.contentRect.width * CGFloat(filter.pointPixelScale))
        configuration.height = Int(filter.contentRect.height * CGFloat(filter.pointPixelScale))
        configuration.ignoreShadowsSingleWindow = true
        configuration.showsCursor = false
        SCScreenshotManager.captureImage(contentFilter: filter, configuration: configuration) { captured, error in
            image = captured
            said = error.map { "\($0)" } ?? "window on screen \(window.isOnScreen)"
            done.signal()
        }
    }
    done.wait()
    return (image, said)
}

func captureWindow(
    id windowId: Int, window: AXUIElement, crop: CGRect?, to path: String, pid: pid_t
) throws {
    var captured: CGImage?
    var said = ""
    // A window not yet drawn captures on a later try.
    for _ in 0..<windowAttempts {
        (captured, said) = captureWindowImage(id: windowId)
        if captured != nil { break }
        Thread.sleep(forTimeInterval: retryPauseSeconds)
    }
    let counts = countNumbersWindows(pid: pid)
    let hidden = NSRunningApplication(processIdentifier: pid)?.isHidden ?? false
    writeLog("captured \((path as NSString).lastPathComponent): \(captured != nil) (\(said)), "
        + "Numbers hidden \(hidden), windows on screen \(counts.onScreen) of \(counts.all)")
    let failure = HelperFailure(problem: HelperProblem(
        kind: "capture",
        detail: "the Numbers window could not be captured to \((path as NSString).lastPathComponent): \(said)",
        remedy: "check Screen Recording for pybersdev-golden-confirm, then rerun"))
    guard var image = captured else { throw failure }
    if let crop, let frame = readFrame(window), frame.width > 0 {
        let scale = CGFloat(image.width) / frame.width
        let pixels = CGRect(
            x: (crop.minX - frame.minX) * scale, y: (crop.minY - frame.minY) * scale,
            width: crop.width * scale, height: crop.height * scale).integral
        guard let cropped = image.cropping(to: pixels) else { throw failure }
        image = cropped
    }
    guard let destination = CGImageDestinationCreateWithURL(
        URL(fileURLWithPath: path) as CFURL, UTType.png.identifier as CFString, 1, nil)
    else { throw failure }
    CGImageDestinationAddImage(destination, image, nil)
    guard CGImageDestinationFinalize(destination) else { throw failure }
}

func findDataFormatFrame(in window: AXUIElement) -> CGRect? {
    let elements = collectElements(window)
    guard let tabs = elements.first(where: {
        readText($0, kAXRoleAttribute) == kAXRadioButtonRole
            && readText($0, kAXDescriptionAttribute) == "Table"
    }).flatMap(readFrame),
          let windowFrame = readFrame(window)
    else { return nil }
    let end = elements.first(where: {
        readText($0, kAXRoleAttribute) == kAXDisclosureTriangleRole
    }).flatMap(readFrame)
    let top = tabs.minY - 8
    let bottom = (end?.minY ?? windowFrame.maxY) - 8
    let left = tabs.minX - 6
    return CGRect(x: left, y: top, width: windowFrame.maxX - left, height: bottom - top)
}

func formatCaptureName(_ parts: [String]) -> String {
    let joined = parts.joined(separator: "-").lowercased()
    let kept = joined.map { $0.isLetter || $0.isNumber ? $0 : "-" }
    return String(kept) + ".png"
}

// MARK: Operations

func runPermissionsCheck(_ request: HelperRequest) -> HelperResult {
    var result = HelperResult(sourceHash: readSourceHash(), operation: request.operation.rawValue)
    result.problems = findSessionProblems() + findGrantProblems()
    if let automation = findAutomationProblem() { result.problems.append(automation) }
    return result
}

func readNumbersHidden(pid: pid_t) -> Bool {
    (readAttribute(AXUIElementCreateApplication(pid), kAXHiddenAttribute) as? Bool) ?? false
}

// Hidden, Numbers stays out of the developer's way and still draws what the helper captures.
@discardableResult
func setNumbersHidden(pid: pid_t, _ hidden: Bool) -> Bool {
    let status = AXUIElementSetAttributeValue(
        AXUIElementCreateApplication(pid), kAXHiddenAttribute as CFString,
        (hidden ? kCFBooleanTrue : kCFBooleanFalse) as CFTypeRef)
    writeLog("set Numbers hidden \(hidden): status \(status.rawValue)")
    return status == .success
}

func launchNumbers() throws -> (NSRunningApplication, Bool) {
    if let running = NSRunningApplication.runningApplications(
        withBundleIdentifier: numbersBundleIdentifier).first {
        return (running, false)
    }
    guard let url = NSWorkspace.shared.urlForApplication(withBundleIdentifier: numbersBundleIdentifier)
    else {
        throw HelperFailure(problem: HelperProblem(
            kind: "numbers",
            detail: "Numbers is not installed",
            remedy: "install Numbers from the App Store"))
    }
    let configuration = NSWorkspace.OpenConfiguration()
    configuration.activates = false
    configuration.hides = true
    var launched: NSRunningApplication?
    let done = DispatchSemaphore(value: 0)
    NSWorkspace.shared.openApplication(at: url, configuration: configuration) { application, _ in
        launched = application
        done.signal()
    }
    done.wait()
    guard let launched else {
        throw HelperFailure(problem: HelperProblem(
            kind: "numbers", detail: "Numbers did not launch", remedy: "open Numbers once by hand"))
    }
    // Numbers answers Apple Events only once it has finished launching.
    var attempts = 0
    while (try? runAppleScript("get name")) == nil, attempts < 60 {
        Thread.sleep(forTimeInterval: 0.5)
        attempts += 1
    }
    return (launched, true)
}

// Addressing Numbers after it has crashed would launch it again, so its process is checked.
func checkProcessEnded(pid: pid_t) -> Bool {
    for _ in 0..<windowAttempts {
        if kill(pid, 0) != 0 { return true }
        Thread.sleep(forTimeInterval: retryPauseSeconds)
    }
    return false
}

// A run that launched Numbers quits it, unless someone has since begun unsaved work there.
func quitNumbersLaunched(_ launched: Bool, numbers: NSRunningApplication) {
    let pid = numbers.processIdentifier
    guard launched, kill(pid, 0) == 0 else { return }
    do {
        try checkNoUnsavedDocuments(timeoutSeconds: quitTimeoutSeconds)
        _ = try runAppleScript("close every document saving no\nquit", timeoutSeconds: quitTimeoutSeconds)
        if checkProcessEnded(pid: pid) {
            writeLog("quit Numbers")
            return
        }
    } catch is HelperFailure {
        writeLog("left Numbers running: it holds unsaved work")
        return
    } catch {
        writeLog("Numbers did not answer: \(error)")
    }
    // A damaged golden can leave the Numbers this run launched hung, holding nothing of anyone's.
    numbers.forceTerminate()
    writeLog("force-quit the Numbers this run launched: \(checkProcessEnded(pid: pid))")
}

func dismissAlerts(_ alerts: [AXUIElement]) {
    for alert in alerts {
        let cancel = readAttribute(alert, kAXCancelButtonAttribute)
        let fallback = readAttribute(alert, kAXDefaultButtonAttribute)
        if let button = (cancel ?? fallback).map({ $0 as! AXUIElement }) {
            AXUIElementPerformAction(button, kAXPressAction as CFString)
        }
    }
}

func runDocumentInspect(_ request: HelperRequest) -> HelperResult {
    var result = HelperResult(sourceHash: readSourceHash(), operation: request.operation.rawValue)
    result.problems = findSessionProblems() + findGrantProblems()
    guard result.problems.isEmpty else { return result }
    do {
        let documentPath = try checkTemporaryPath(request.documentPath, field: "documentPath")
        let savedCopyPath = try checkTemporaryPath(request.savedCopyPath, field: "savedCopyPath")
        let captureDirectory = try checkCaptureDirectory(request.captureDirectory)
        let cells = request.cells ?? []
        let sheets = cells.map(\.sheet).reduce(into: [String]()) { if !$0.contains($1) { $0.append($1) } }
        let captureCount = sheets.count + cells.count
        guard captureCount <= (request.maxCaptures ?? 0) else {
            throw HelperFailure(problem: HelperProblem(
                kind: "captureLimit",
                detail: "this run needs \(captureCount) captures, over the limit of \(request.maxCaptures ?? 0)",
                remedy: "check fewer cells in one run"))
        }
        if request.freshNumbers == true, !NSRunningApplication.runningApplications(
            withBundleIdentifier: numbersBundleIdentifier).isEmpty {
            throw HelperFailure(problem: HelperProblem(
                kind: "numbersRunning",
                detail: "Numbers is already running, and a damaged document can hang it",
                remedy: "quit Numbers, then rerun"))
        }
        writeLog("launching Numbers")
        let (numbers, launched) = try launchNumbers()
        result.launchedNumbers = launched
        if launched { numbersLaunchedByRun = numbers }
        writeLog("Numbers pid \(numbers.processIdentifier), launched by this run: \(launched)")
        defer { quitNumbersLaunched(launched, numbers: numbers) }
        let wasHidden = readNumbersHidden(pid: numbers.processIdentifier)
        var hideAttempts = 0
        while !setNumbersHidden(pid: numbers.processIdentifier, true), hideAttempts < windowAttempts {
            Thread.sleep(forTimeInterval: retryPauseSeconds)
            hideAttempts += 1
        }
        // A Numbers the developer already had open is shown again as it was found.
        defer {
            if !launched, !wasHidden, kill(numbers.processIdentifier, 0) == 0 {
                setNumbersHidden(pid: numbers.processIdentifier, false)
            }
        }
        writeLog("checking Automation")
        try checkAutomationPermission()
        try checkNoUnsavedDocuments()
        result.numbersVersion = try? runAppleScript("get version").stringValue
        try inspectDocument(
            documentPath: documentPath, savedCopyPath: savedCopyPath,
            captureDirectory: captureDirectory, cells: cells, tables: request.tables ?? [],
            sheets: sheets, numbers: numbers, result: &result)
    } catch let failure as HelperFailure {
        result.problems.append(failure.problem)
    } catch let failure as AppleScriptError {
        result.problems.append(HelperProblem(
            kind: "appleScript",
            detail: "Numbers answered error \(failure.number): \(failure.message)",
            remedy: "look at Numbers for a dialog, then rerun"))
    } catch {
        result.problems.append(HelperProblem(
            kind: "helper", detail: String(describing: error), remedy: "rerun, then read the log"))
    }
    return result
}

func inspectDocument(
    documentPath: String, savedCopyPath: String, captureDirectory: String,
    cells: [CellAddress], tables: [TableAddress], sheets: [String],
    numbers: NSRunningApplication, result: inout HelperResult
) throws {
    let documentId: String
    let existingWindows = readNumbersWindows(pid: numbers.processIdentifier)
    do {
        let opened = try runAppleScript(
            "set opened to open (POSIX file \(quoteAppleScript(documentPath)))\n"
                + "if opened is missing value then return missing value\n"
                + "return id of opened")
        Thread.sleep(forTimeInterval: 1.0)
        let alerts = findAlerts(pid: numbers.processIdentifier, excluding: existingWindows)
        result.alertText = readAlertText(alerts)
        guard let id = readOptionalText(opened) else {
            result.openOutcome = result.alertText.isEmpty ? "refused" : "alert"
            dismissAlerts(alerts)
            throw HelperFailure(problem: HelperProblem(
                kind: "open",
                detail: "Numbers did not open the document"
                    + (result.alertText.isEmpty ? "" : ": " + result.alertText.joined(separator: " ")),
                remedy: "open a copy by hand to see what Numbers reports"))
        }
        documentId = id
    } catch let failure as AppleScriptError {
        // A dropped connection means Numbers died, however long its crash report keeps the process.
        let crashed = failure.number == connectionInvalidError
            || checkProcessEnded(pid: numbers.processIdentifier)
        writeLog("open failed with \(failure.number), process alive: \(kill(numbers.processIdentifier, 0) == 0)")
        if !crashed {
            let alerts = findAlerts(pid: numbers.processIdentifier, excluding: existingWindows)
            result.alertText = readAlertText(alerts)
            dismissAlerts(alerts)
        }
        result.openOutcome = crashed ? "crashed" : result.alertText.isEmpty ? "refused" : "alert"
        let alert = result.alertText.joined(separator: " ")
        throw HelperFailure(problem: HelperProblem(
            kind: "open",
            detail: crashed
                ? "Numbers crashed while opening the document (error \(failure.number))"
                : alert.isEmpty
                    ? "Numbers refused the document: \(failure.message)"
                    : "Numbers showed an alert while opening: \(alert)",
            remedy: "open a copy by hand to see what Numbers reports"))
    }
    guard result.alertText.isEmpty else {
        result.openOutcome = "alert"
        dismissAlerts(findAlerts(pid: numbers.processIdentifier, excluding: existingWindows))
        _ = try? runAppleScript("close (document id \(quoteAppleScript(documentId))) saving no")
        throw HelperFailure(problem: HelperProblem(
            kind: "open",
            detail: "Numbers warned while opening: " + result.alertText.joined(separator: " "),
            remedy: "open a copy by hand to read the whole alert"))
    }
    result.openOutcome = "opened"
    writeLog("opened \(documentId)")
    // Opening a document can bring Numbers back into view.
    setNumbersHidden(pid: numbers.processIdentifier, true)
    defer {
        if kill(numbers.processIdentifier, 0) == 0 {
            _ = try? runAppleScript("close (document id \(quoteAppleScript(documentId))) saving no")
        }
    }

    let document = "document id \(quoteAppleScript(documentId))"
    let (windowId, window) = try findDocumentWindow(documentId: documentId, pid: numbers.processIdentifier)

    for sheet in sheets {
        let first = cells.first { $0.sheet == sheet }!
        try selectCell(first, documentId: documentId)
        let path = (captureDirectory as NSString).appendingPathComponent(
            formatCaptureName(["sheet", sheet]))
        try captureWindow(
            id: Int(windowId), window: window, crop: nil, to: path, pid: numbers.processIdentifier)
        result.sheetCaptures.append(SheetCapture(sheet: sheet, path: path))
    }

    for address in cells {
        var reading = CellReading(address: address)
        let facts = try runAppleScript(
            "set c to \(formatCellReference(address, documentId: documentId))\n"
                + "return {formatted value of c, formula of c, (format of c) as text, value of c}")
        reading.formattedValue = facts.atIndex(1).flatMap(readOptionalText)
        reading.formula = facts.atIndex(2).flatMap(readOptionalText)
        reading.formatKind = facts.atIndex(3)?.stringValue
        reading.value = facts.atIndex(4).map(readCellValue)
        try selectCell(address, documentId: documentId)
        try openCellTab(in: window)
        reading.dataFormat = try readDataFormat(in: window)
        let path = (captureDirectory as NSString).appendingPathComponent(
            formatCaptureName(["cell", address.sheet, address.table, address.cell]))
        try captureWindow(
            id: Int(windowId), window: window, crop: findDataFormatFrame(in: window), to: path,
            pid: numbers.processIdentifier)
        reading.inspectorCapture = path
        result.cells.append(reading)
    }

    for address in tables {
        result.tables.append(try readTable(address, documentId: documentId))
    }

    _ = try runAppleScript("save \(document) in (POSIX file \(quoteAppleScript(savedCopyPath)))")
    result.savedCopy = FileManager.default.fileExists(atPath: savedCopyPath)
}

// A document's window appears a moment after `open` returns, so the lookup waits for it.
func findDocumentWindow(documentId: String, pid: pid_t) throws -> (Int32, AXUIElement) {
    // A `whose document is` filter fails on Numbers' document-less windows, so each is tried.
    let lookup = "repeat with w in windows\n"
        + "try\n"
        + "if id of document of w is \(quoteAppleScript(documentId)) then return {id of w, name of w}\n"
        + "end try\n"
        + "end repeat\n"
        + "return {0, \"\"}"
    var seen = ""
    for attempt in 0..<windowAttempts {
        let facts = try runAppleScript(lookup)
        seen = facts.atIndex(2)?.stringValue ?? ""
        if let windowId = facts.atIndex(1)?.int32Value, windowId != 0,
           let window = findNumbersWindow(named: seen, pid: pid) {
            return (windowId, window)
        }
        // A window just opened can be off screen for a moment, so the desktop check waits.
        if attempt >= otherDesktopAttempts { try checkNumbersOnThisDesktop(pid: pid) }
        Thread.sleep(forTimeInterval: retryPauseSeconds)
    }
    throw HelperFailure(problem: HelperProblem(
        kind: "window",
        detail: "the opened document's window \(seen.isEmpty ? "never appeared" : "'\(seen)' was not reachable through Accessibility")",
        remedy: "keep the Numbers window out of full screen and not minimized, then rerun"))
}

// Row by row, so each name's position in the grid is explicit rather than inferred from order.
func readTable(_ address: TableAddress, documentId: String) throws -> TableReading {
    let facts = try runAppleScript(
        "set t to table \(quoteAppleScript(address.table)) of sheet \(quoteAppleScript(address.sheet)) "
            + "of document id \(quoteAppleScript(documentId))\n"
            + "set names to {}\n"
            + "repeat with r in rows of t\n"
            + "set end of names to name of cells of r\n"
            + "end repeat\n"
            + "return {row count of t, column count of t, names}")
    let rows = facts.atIndex(3)
    let cellNames = (0..<(rows?.numberOfItems ?? 0)).map { row in
        let names = rows?.atIndex(row + 1)
        return (0..<(names?.numberOfItems ?? 0)).map { names?.atIndex($0 + 1)?.stringValue ?? "" }
    }
    return TableReading(
        address: address, rowCount: Int(facts.atIndex(1)?.int32Value ?? 0),
        columnCount: Int(facts.atIndex(2)?.int32Value ?? 0), cellNames: cellNames)
}

func selectCell(_ address: CellAddress, documentId: String) throws {
    let document = "document id \(quoteAppleScript(documentId))"
    _ = try runAppleScript(
        "set t to table \(quoteAppleScript(address.table)) of sheet \(quoteAppleScript(address.sheet)) of \(document)\n"
            + "set active sheet of \(document) to sheet \(quoteAppleScript(address.sheet)) of \(document)\n"
            + "set selection range of t to range \(quoteAppleScript(address.cell + ":" + address.cell)) of t")
    Thread.sleep(forTimeInterval: 0.5)
}

func runRequest(at requestPath: String) {
    guard let data = FileManager.default.contents(atPath: requestPath),
          let request = try? JSONDecoder().decode(HelperRequest.self, from: data)
    else {
        FileHandle.standardError.write(Data("unreadable request: \(requestPath)\n".utf8))
        exit(2)
    }
    // Numbers can hang on a damaged file, so the helper owns its deadline rather than the script.
    DispatchQueue.global().asyncAfter(deadline: .now() + request.deadlineSeconds) {
        var result = HelperResult(sourceHash: readSourceHash(), operation: request.operation.rawValue)
        result.problems = [HelperProblem(
            kind: "deadline",
            detail: "the helper did not finish within \(Int(request.deadlineSeconds)) seconds",
            remedy: "look at Numbers for a dialog or a hang, then rerun")]
        numbersLaunchedByRun?.forceTerminate()
        writeResult(result, to: request.resultPath)
        exit(3)
    }
    let result: HelperResult
    switch request.operation {
    case .permissionsCheck:
        result = runPermissionsCheck(request)
    case .documentInspect:
        result = runDocumentInspect(request)
    }
    writeResult(result, to: request.resultPath)
}

guard CommandLine.arguments.count == 2 else {
    FileHandle.standardError.write(Data("usage: pybersdev-golden-confirm <request.json>\n".utf8))
    exit(2)
}
runRequest(at: CommandLine.arguments[1])
