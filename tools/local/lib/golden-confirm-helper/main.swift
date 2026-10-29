// pybersdev-golden-confirm
//
// The background app that holds Accessibility and Screen Recording for
// tools/local/golden_confirm.py, so that Terminal holds neither (PYB-94 AC 11). macOS
// judges a program Terminal starts directly by Terminal's grants, so this is an app
// started with `open`, reading one request file and writing one result file.
//
// It performs only the operations named in `HelperOperation` and never runs a script
// or command it is given (PYB-94 AC 15). Every AppleScript it sends is written here,
// and the only values a request places into one are paths, cell names and cell values
// it escapes. A Data Format value is only matched against a menu item or typed into a field.
//
// UPDATES
// 2026-10-29  A failed capture logs every error and the window's state, and Numbers is
//             shown for each capture, which a hidden window refuses, for PYB-272.
// 2026-10-29  A request reads cells as text alone, and a failed capture is a problem that
//             leaves the readings, for PYB-272.
// 2026-10-21  Names each Data Format control, a step sets one by its name, a step extends
//             a table to a cell, and a step builds a custom format, for PYB-219.
// 2026-09-30  Reads a date at the zone's offset now, which Numbers applies to every date, for PYB-137.
// 2026-09-29  Edits copies of documents through named steps, to make a measurement, for PYB-118.
// 2026-09-22  Reads a table's size and cell names, and names a closed Numbers, for PYB-111.
// 2026-09-22  Waits for the Data Format section and for a capture stream to recover.
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
// A capture stream that failed to start stayed failed through 11 s of 0.5 s retries, 2026-09-22.
let streamRetryPauseSeconds = 2.0
let streamStartFailedError = -3811
// The Numbers this run launched, which the deadline force-quits because nothing else will.
nonisolated(unsafe) var numbersLaunchedByRun: NSRunningApplication?
// The four-character code AppleScript uses for missing value, which Swift does not import.
let missingValueCode: OSType = 0x6D73_6E67

// MARK: Request and result

enum HelperOperation: String, Codable {
    case permissionsCheck
    case documentInspect
    case documentEdit
}

// Every menu item a step may press, each spelled here so a request names none of its own.
enum EditMenuItem: String, Codable {
    case copy
    case paste
    case delete
    case autofillDown

    var path: [String] {
        switch self {
        case .copy: return ["Edit", "Copy"]
        case .paste: return ["Edit", "Paste"]
        case .delete: return ["Edit", "Delete"]
        case .autofillDown: return ["Table", "Autofill Cells", "Autofill Down"]
        }
    }
}

enum EditCellFormat: String, Codable {
    case checkbox
}

enum EditAction: String, Codable {
    case select
    case menuPress
    case formatSet
    case valueSet
    case dataFormatSet
    case tableExtend
    case tableAdd
    case sheetAdd
    case customFormatEdit
}

// `document` counts the request's `documentPaths` from zero; the first is the one saved.
struct EditStep: Codable {
    let action: EditAction
    let document: Int
    var sheet: String?
    var table: String?
    var range: String?
    var menuItem: EditMenuItem?
    var format: EditCellFormat?
    var value: String?
    var setting: String?
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
    // Read each cell through AppleScript alone, with no inspector and no capture.
    var textOnly: Bool?
    var freshNumbers: Bool?
    var documentPaths: [String]?
    var steps: [EditStep]?
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
    var setting: String = ""
}

struct DataFormatControl {
    let element: AXUIElement
    let frame: CGRect
    var reading: InspectorElement
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
    let cellFacts: [[CellFact]]
}

// What AppleScript answers for one cell without the inspector, so every cell is read.
struct CellFact: Codable {
    let value: CellValue
    let formula: String?
    let formatKind: String?
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
    var stepsDone: Int?
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
            remedy: "run the helper only through the golden confirmation"))
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
            remedy: "run the helper only through the golden confirmation"))
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
        // Numbers hands back a date built at today's offset, so a winter date read at its own
        // offset comes out an hour early wherever the zone keeps daylight saving time.
        formatter.timeZone = TimeZone(secondsFromGMT: TimeZone.current.secondsFromGMT())
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

// The format-kind popup sits before its own "Data Format" heading, so the walk starts at the tabs.
func findDataFormatStart(_ elements: [AXUIElement]) -> Int? {
    guard let start = elements.firstIndex(where: {
        readText($0, kAXRoleAttribute) == kAXRadioButtonRole
            && readText($0, kAXDescriptionAttribute) == "Arrange"
    }), elements[start...].contains(where: {
        readText($0, kAXRoleAttribute) == kAXStaticTextRole
            && readText($0, kAXValueAttribute) == "Data Format"
    }) else { return nil }
    return start
}

// The Cell tab can fill in after its press returns, so its section is awaited rather than assumed.
func readDataFormatControls(in window: AXUIElement) throws -> [DataFormatControl] {
    var elements = collectElements(window)
    var rereads = 0
    while findDataFormatStart(elements) == nil, rereads < windowAttempts {
        Thread.sleep(forTimeInterval: retryPauseSeconds)
        rereads += 1
        elements = collectElements(window)
    }
    if rereads > 0 { writeLog("Data Format section read again \(rereads) times") }
    guard let start = findDataFormatStart(elements) else {
        if let locked = findSessionProblems().first { throw HelperFailure(problem: locked) }
        let texts = elements.filter { readText($0, kAXRoleAttribute) == kAXStaticTextRole }
            .map { readText($0, kAXValueAttribute) }.filter { !$0.isEmpty }
        writeLog("no Data Format section; the window's texts begin " + texts.prefix(20).joined(separator: " | "))
        // The Cell tab was found by its English name, so a missing section is not a language problem.
        throw HelperFailure(problem: HelperProblem(
            kind: "inspector",
            detail: "the Cell tab showed no Data Format section within "
                + "\(Int(Double(windowAttempts) * retryPauseSeconds)) seconds",
            remedy: "rerun, then read helper.log"))
    }
    var section: [DataFormatControl] = []
    for element in elements[(start + 1)...] {
        let role = readText(element, kAXRoleAttribute)
        if role == kAXDisclosureTriangleRole { break }
        if role == kAXStaticTextRole, ["Fill", "Border"].contains(readText(element, kAXValueAttribute)) {
            break
        }
        guard [kAXStaticTextRole, kAXTextFieldRole, kAXPopUpButtonRole, kAXCheckBoxRole,
               kAXRadioButtonRole].contains(role) else { continue }
        section.append(DataFormatControl(
            element: element, frame: readFrame(element) ?? .zero,
            reading: InspectorElement(
                role: role,
                title: readText(element, kAXTitleAttribute),
                label: readText(element, kAXDescriptionAttribute),
                value: readText(element, kAXValueAttribute))))
    }
    section = orderOnScreen(section)
    nameDataFormatControls(&section)
    return section
}

let rowTolerance: CGFloat = 8

let captionGap: CGFloat = 12

func orderOnScreen(_ section: [DataFormatControl]) -> [DataFormatControl] {
    let placed = section.sorted { $0.frame.midY < $1.frame.midY }
    var rows: [[DataFormatControl]] = []
    for control in placed {
        if let first = rows.last?.first, abs(control.frame.midY - first.frame.midY) < rowTolerance {
            rows[rows.count - 1].append(control)
        } else {
            rows.append([control])
        }
    }
    return rows.flatMap { $0.sorted { $0.frame.minX < $1.frame.minX } }
}

func readDataFormat(in window: AXUIElement) throws -> [InspectorElement] {
    try readDataFormatControls(in: window).map(\.reading)
}

// By position, since Currency lists its Decimals field last in the tree.
func nameDataFormatControls(_ section: inout [DataFormatControl]) {
    let texts = section.filter { $0.reading.role == kAXStaticTextRole }
    var namedDataFormat = false
    var unlabeled = 0
    for position in section.indices where section[position].reading.role != kAXStaticTextRole {
        let control = section[position]
        let reading = control.reading
        let name: String
        if reading.role == kAXPopUpButtonRole, !namedDataFormat {
            name = "Data Format"
            namedDataFormat = true
        } else if reading.role == kAXCheckBoxRole {
            name = (reading.title.isEmpty ? reading.label : reading.title)
                .trimmingCharacters(in: .whitespacesAndNewlines)
        } else if let label = findRowLabel(of: control, in: section) {
            name = label
        } else if let caption = texts.first(where: { isCaption($0, of: control) }) {
            name = caption.reading.value
        } else if reading.role == kAXTextFieldRole {
            name = "Items"
        } else {
            unlabeled += 1
            name = "Unlabeled \(reading.role.dropFirst(2)) \(unlabeled)"
        }
        section[position].reading.setting = name
    }
}

let labelOverlap: CGFloat = 2

// Only the first control after a label takes it, so the negative style beside Decimals does not.
func findRowLabel(of control: DataFormatControl, in section: [DataFormatControl]) -> String? {
    let left = section.filter {
        abs($0.frame.midY - control.frame.midY) < rowTolerance && $0.frame.maxX <= control.frame.minX + labelOverlap
    }
    guard let nearest = left.max(by: { $0.frame.maxX < $1.frame.maxX }),
          nearest.reading.role == kAXStaticTextRole, nearest.reading.value.hasSuffix(":")
    else { return nil }
    return String(nearest.reading.value.dropLast())
}

func isCaption(_ text: DataFormatControl, of control: DataFormatControl) -> Bool {
    let value = text.reading.value
    return !value.hasSuffix(":") && value != "–" && !value.isEmpty
        && text.frame.minY >= control.frame.maxY - rowTolerance
        && text.frame.minY - control.frame.maxY < captionGap
        && text.frame.midX >= control.frame.minX && text.frame.midX <= control.frame.maxX
}

func describeDataFormat(_ section: [DataFormatControl]) -> String {
    section.map {
        let role = $0.reading.role.dropFirst(2)
        return $0.reading.setting.isEmpty
            ? "\(role) '\($0.reading.value)'" : "\($0.reading.setting) \(role) = '\($0.reading.value)'"
    }.joined(separator: ", ")
}

// MARK: Custom formats

let deleteKey: CGKeyCode = 51
let escapeKey: CGKeyCode = 53
let rightArrowKey: CGKeyCode = 124
let leftArrowKey: CGKeyCode = 123
let aKey: CGKeyCode = 0

func failCustomFormat(_ detail: String) -> HelperFailure {
    HelperFailure(problem: HelperProblem(
        kind: "customFormat", detail: detail, remedy: "look at the Create Custom Format dialog, then rerun"))
}

func openCustomFormat(in window: AXUIElement) throws {
    guard let popUp = try readDataFormatControls(in: window).first(where: { $0.reading.setting == "Data Format" })
    else { throw failCustomFormat("the Data Format menu was not found") }
    try choosePopUpItem(popUp.element, title: "Create Custom Format…", setting: "Data Format")
    Thread.sleep(forTimeInterval: 1.0)
    _ = try findCustomFormatSheet(in: window)
}

func findCustomFormatSheet(in window: AXUIElement) throws -> AXUIElement {
    let sheets = (readAttribute(window, kAXChildrenAttribute) as? [AXUIElement] ?? [])
        .filter { readText($0, kAXRoleAttribute) == kAXSheetRole }
    guard let sheet = sheets.first(where: { findFormatField(in: $0) != nil }) else {
        throw failCustomFormat("the Create Custom Format dialog is not open")
    }
    return sheet
}

// A format field carries this help text, one for the format and one per rule after it.
func listFormatFields(in sheet: AXUIElement) -> [AXUIElement] {
    collectElements(sheet).filter {
        readText($0, kAXRoleAttribute) == kAXTextFieldRole
            && readText($0, kAXHelpAttribute).hasPrefix("Drag tokens")
    }
}

// The newest rule's field, or the format's own while it has no rule, is the one a step edits.
func findFormatField(in sheet: AXUIElement) -> AXUIElement? {
    listFormatFields(in: sheet).last
}

func listRuleMenus(in sheet: AXUIElement) -> [AXUIElement] {
    collectElements(sheet).filter {
        readText($0, kAXRoleAttribute) == kAXPopUpButtonRole
            && readText($0, kAXHelpAttribute).hasPrefix("Change the rule")
    }
}

func listTokens(in field: AXUIElement) -> [AXUIElement] {
    collectElements(field).filter { readText($0, kAXSubroleAttribute) == "AXTextAttachment" }
}

func postKey(_ key: CGKeyCode, flags: CGEventFlags = []) {
    for isDown in [true, false] {
        let event = CGEvent(keyboardEventSource: nil, virtualKey: key, keyDown: isDown)!
        event.flags = flags
        event.post(tap: .cghidEventTap)
    }
    Thread.sleep(forTimeInterval: 0.1)
}

// Focus set through Accessibility stays on a token whose menu just closed, so inserting text starts with a click.
func clickPointer(at point: CGPoint) {
    for type in [CGEventType.leftMouseDown, .leftMouseUp] {
        CGEvent(mouseEventSource: nil, mouseType: type, mouseCursorPosition: point, mouseButton: .left)!
            .post(tap: .cghidEventTap)
    }
    Thread.sleep(forTimeInterval: 0.3)
}

// Accessibility offers no action that drops a token, so the drag is a real one.
func dragPointer(from start: CGPoint, to end: CGPoint) {
    CGEvent(mouseEventSource: nil, mouseType: .leftMouseDown, mouseCursorPosition: start, mouseButton: .left)!
        .post(tap: .cghidEventTap)
    for step in 1...20 {
        let fraction = CGFloat(step) / 20
        let point = CGPoint(x: start.x + (end.x - start.x) * fraction, y: start.y + (end.y - start.y) * fraction)
        CGEvent(mouseEventSource: nil, mouseType: .leftMouseDragged, mouseCursorPosition: point, mouseButton: .left)!
            .post(tap: .cghidEventTap)
        Thread.sleep(forTimeInterval: 0.03)
    }
    CGEvent(mouseEventSource: nil, mouseType: .leftMouseUp, mouseCursorPosition: end, mouseButton: .left)!
        .post(tap: .cghidEventTap)
    Thread.sleep(forTimeInterval: 1.0)
}

// A Number palette labels each token, and the Date & Time palette shows only examples.
func findPaletteToken(_ name: String, in sheet: AXUIElement) throws -> AXUIElement {
    let fields = listFormatFields(in: sheet)
    let inField = fields.flatMap(listTokens)
    let placed = collectElements(sheet).filter {
        readText($0, kAXRoleAttribute) == kAXStaticTextRole
            || readText($0, kAXSubroleAttribute) == "AXTextAttachment"
    }.map { element in DataFormatControl(
        element: element, frame: readFrame(element) ?? .zero,
        reading: InspectorElement(role: readText(element, kAXRoleAttribute), title: "", label: "",
                                  value: readText(element, kAXValueAttribute))) }
    let fieldFrames = fields.compactMap(readFrame)
    let palette = placed.filter { control in
        readText(control.element, kAXSubroleAttribute) == "AXTextAttachment"
            && !inField.contains { CFEqual($0, control.element) }
            && !fieldFrames.contains { $0.intersects(control.frame) }
    }
    let named = palette.map { (control: $0, label: findRowLabel(of: $0, in: placed)) }
    guard let token = named.first(where: { $0.label == name || $0.control.reading.value == name }) else {
        let offered = named.map { ($0.label.map { "\($0): " } ?? "") + "'\($0.control.reading.value)'" }
        throw failCustomFormat("the palette holds no \(name) token, among: " + offered.joined(separator: ", "))
    }
    return token.control.element
}

// A token's menu opens inside the document window, which keeps the menu bar out of the search.
func chooseTokenItem(_ token: AXUIElement, title: String, window: AXUIElement) throws {
    AXUIElementPerformAction(token, "AXShowMenu" as CFString)
    Thread.sleep(forTimeInterval: 0.5)
    let menus = collectElements(window).filter { readText($0, kAXRoleAttribute) == kAXMenuRole }
    let items = menus.flatMap(collectElements).filter { readText($0, kAXRoleAttribute) == kAXMenuItemRole }
    guard let item = items.first(where: { readText($0, kAXTitleAttribute) == title }) else {
        postKey(escapeKey)
        let titles = items.map { readText($0, kAXTitleAttribute) }.filter { !$0.isEmpty }
        throw failCustomFormat("the token's menu holds no '\(title)', among: " + titles.joined(separator: ", "))
    }
    AXUIElementPerformAction(item, kAXPressAction as CFString)
    Thread.sleep(forTimeInterval: 0.5)
}

// Nil when the menu marks no item at all, as the date tokens' menus do, so nothing can be read back.
func readTokenItemMarked(_ token: AXUIElement, title: String, window: AXUIElement) -> Bool? {
    AXUIElementPerformAction(token, "AXShowMenu" as CFString)
    Thread.sleep(forTimeInterval: 0.5)
    let items = collectElements(window).filter { readText($0, kAXRoleAttribute) == kAXMenuRole }
        .flatMap(collectElements).filter { readText($0, kAXRoleAttribute) == kAXMenuItemRole }
    let marked = items.filter { !readText($0, kAXMenuItemMarkCharAttribute).isEmpty }
    postKey(escapeKey)
    return marked.isEmpty ? nil : marked.contains { readText($0, kAXTitleAttribute) == title }
}

// A toggle such as Hide Separator is retitled rather than marked, so a changed token also counts.
func applyTokenItem(_ title: String, to token: AXUIElement, field: AXUIElement, window: AXUIElement) throws {
    let before = readText(token, kAXValueAttribute)
    try chooseTokenItem(token, title: title, window: window)
    guard let after = listTokens(in: field).last else { throw failCustomFormat("the token vanished") }
    if readText(after, kAXValueAttribute) != before { return }
    guard readTokenItemMarked(after, title: title, window: window) != false else {
        throw failCustomFormat("the token did not take '\(title)', and still reads '\(before)'")
    }
}

// Each part reads back what it changed, so a dialog that ignored a step fails it.
func editCustomFormat(_ part: String, value: String, in window: AXUIElement) throws {
    let sheet = try findCustomFormatSheet(in: window)
    guard let field = findFormatField(in: sheet) else { throw failCustomFormat("the format field is missing") }
    switch part {
    case "Name":
        guard let name = collectElements(sheet).first(where: {
            readText($0, kAXRoleAttribute) == kAXTextFieldRole
                && readText($0, kAXHelpAttribute).hasPrefix("Type a name")
        }) else { throw failCustomFormat("the Name field is missing") }
        AXUIElementSetAttributeValue(name, kAXValueAttribute as CFString, value as CFString)
        guard readText(name, kAXValueAttribute) == value else {
            throw failCustomFormat("the Name field reads '\(readText(name, kAXValueAttribute))'")
        }
    case "Type":
        guard let menu = collectElements(sheet).first(where: {
            readText($0, kAXRoleAttribute) == kAXPopUpButtonRole
                && readText($0, kAXHelpAttribute).hasPrefix("Choose a type")
        }) else { throw failCustomFormat("the Type menu is missing") }
        try choosePopUpItem(menu, title: value, setting: "Type")
        Thread.sleep(forTimeInterval: 0.5)
        guard readText(menu, kAXValueAttribute) == value else {
            throw failCustomFormat("the Type menu reads '\(readText(menu, kAXValueAttribute))'")
        }
    case "Clear":
        AXUIElementSetAttributeValue(field, kAXFocusedAttribute as CFString, kCFBooleanTrue)
        postKey(aKey, flags: .maskCommand)
        postKey(deleteKey)
        guard readText(field, kAXValueAttribute).isEmpty else {
            throw failCustomFormat("the format field still reads '\(readText(field, kAXValueAttribute))'")
        }
    case "Text", "TextBefore":
        guard let frame = readFrame(field) else { throw failCustomFormat("the format field has no position") }
        clickPointer(at: CGPoint(x: frame.maxX - 4, y: frame.midY))
        postKey(part == "Text" ? rightArrowKey : leftArrowKey, flags: .maskCommand)
        AXUIElementSetAttributeValue(field, kAXSelectedTextAttribute as CFString, value as CFString)
        Thread.sleep(forTimeInterval: 0.5)
        let shown = readText(field, kAXValueAttribute)
        guard part == "Text" ? shown.hasSuffix(value) : shown.hasPrefix(value) else {
            throw failCustomFormat("the format field reads '\(readText(field, kAXValueAttribute))'")
        }
    case "Rule":
        let rulesBefore = listRuleMenus(in: sheet).count
        guard let add = collectElements(sheet).first(where: {
            readText($0, kAXRoleAttribute) == kAXButtonRole && readText($0, kAXTitleAttribute) == "Add a Rule"
        }) else { throw failCustomFormat("the Add a Rule button is missing") }
        AXUIElementPerformAction(add, kAXPressAction as CFString)
        Thread.sleep(forTimeInterval: 1.0)
        let menus = listRuleMenus(in: try findCustomFormatSheet(in: window))
        guard menus.count == rulesBefore + 1, let menu = menus.last else {
            throw failCustomFormat("Add a Rule left \(menus.count) rules")
        }
        try choosePopUpItem(menu, title: value, setting: "Rule")
        Thread.sleep(forTimeInterval: 0.5)
        guard readText(menu, kAXValueAttribute) == value else {
            throw failCustomFormat("the rule reads '\(readText(menu, kAXValueAttribute))'")
        }
    case "RuleValue":
        guard let input = collectElements(sheet).last(where: {
            readText($0, kAXRoleAttribute) == kAXTextFieldRole
                && readText($0, kAXHelpAttribute).hasPrefix("Type a value for this rule")
        }) else { throw failCustomFormat("no rule has a value field") }
        AXUIElementSetAttributeValue(input, kAXFocusedAttribute as CFString, kCFBooleanTrue)
        AXUIElementSetAttributeValue(input, kAXValueAttribute as CFString, value as CFString)
        AXUIElementPerformAction(input, kAXConfirmAction as CFString)
        Thread.sleep(forTimeInterval: 0.5)
        // The field groups its digits as it shows them, so 1000 reads back as 1,000.
        guard readText(input, kAXValueAttribute).replacingOccurrences(of: ",", with: "") == value else {
            throw failCustomFormat("the rule's value reads '\(readText(input, kAXValueAttribute))'")
        }
    case "Token":
        guard let last = listTokens(in: field).last else { throw failCustomFormat("the format field holds no token") }
        try applyTokenItem(value, to: last, field: field, window: window)
    case "OK":
        guard let ok = collectElements(sheet).first(where: {
            readText($0, kAXRoleAttribute) == kAXButtonRole && readText($0, kAXTitleAttribute) == "OK"
        }) else { throw failCustomFormat("the OK button is missing") }
        AXUIElementPerformAction(ok, kAXPressAction as CFString)
        Thread.sleep(forTimeInterval: 1.0)
        let open = (readAttribute(window, kAXChildrenAttribute) as? [AXUIElement] ?? [])
            .contains { readText($0, kAXRoleAttribute) == kAXSheetRole && findFormatField(in: $0) != nil }
        if open { throw failCustomFormat("the dialog stayed open after OK: " + readAlertText([sheet]).joined(separator: " ")) }
    default:
        let before = listTokens(in: field).count
        let token = try findPaletteToken(part, in: sheet)
        guard let from = readFrame(token), let to = readFrame(field) else {
            throw failCustomFormat("the \(part) token has no position on screen")
        }
        dragPointer(from: CGPoint(x: from.midX, y: from.midY), to: CGPoint(x: to.maxX - 8, y: to.midY))
        let tokens = listTokens(in: field)
        guard tokens.count == before + 1, let dropped = tokens.last else {
            throw failCustomFormat("dragging the \(part) token left the field with \(tokens.count) tokens")
        }
        if !value.isEmpty { try applyTokenItem(value, to: dropped, field: field, window: window) }
    }
}

// Two negative styles are both titled (100), red and plain, so `(100) #2` names the second.
func readItemChoice(_ value: String) -> (title: String, occurrence: Int) {
    guard let marker = value.range(of: " #", options: .backwards),
          let occurrence = Int(value[marker.upperBound...]), occurrence > 0
    else { return (value, 1) }
    return (String(value[..<marker.lowerBound]), occurrence)
}

func choosePopUpItem(_ popUp: AXUIElement, title choice: String, setting: String) throws {
    let (title, occurrence) = readItemChoice(choice)
    AXUIElementPerformAction(popUp, kAXPressAction as CFString)
    Thread.sleep(forTimeInterval: 0.5)
    let items = (readAttribute(popUp, kAXChildrenAttribute) as? [AXUIElement] ?? [])
        .filter { readText($0, kAXRoleAttribute) == kAXMenuRole }
        .flatMap { readAttribute($0, kAXChildrenAttribute) as? [AXUIElement] ?? [] }
    let matching = items.filter { readText($0, kAXTitleAttribute) == title }
    guard matching.count >= occurrence else {
        // A menu left open blocks every AppleScript after it, so Escape follows the cancel.
        AXUIElementPerformAction(popUp, kAXCancelAction as CFString)
        postKey(escapeKey)
        let titles = items.map { readText($0, kAXTitleAttribute) }.filter { !$0.isEmpty }
        throw HelperFailure(problem: HelperProblem(
            kind: "dataFormat",
            detail: "the '\(setting)' menu holds no '\(choice)', among: " + titles.joined(separator: ", "),
            remedy: "name an item the menu lists, then rerun"))
    }
    AXUIElementPerformAction(matching[occurrence - 1], kAXPressAction as CFString)
}

// Read back afterward, so a control Numbers did not take fails the step rather than the fixture.
func setDataFormatControl(_ setting: String, to value: String, in window: AXUIElement) throws {
    let section = try readDataFormatControls(in: window)
    guard let control = section.first(where: { $0.reading.setting == setting }) else {
        throw HelperFailure(problem: HelperProblem(
            kind: "dataFormat",
            detail: "no Data Format setting '\(setting)' among: " + describeDataFormat(section),
            remedy: "name a setting the Data Format section shows for this format, then rerun"))
    }
    switch control.reading.role {
    case kAXPopUpButtonRole:
        try choosePopUpItem(control.element, title: value, setting: setting)
    case kAXCheckBoxRole, kAXRadioButtonRole:
        if control.reading.value != value {
            AXUIElementPerformAction(control.element, kAXPressAction as CFString)
        }
    case kAXTextFieldRole:
        AXUIElementSetAttributeValue(control.element, kAXFocusedAttribute as CFString, kCFBooleanTrue)
        AXUIElementSetAttributeValue(control.element, kAXValueAttribute as CFString, value as CFString)
        AXUIElementPerformAction(control.element, kAXConfirmAction as CFString)
    default:
        throw HelperFailure(problem: HelperProblem(
            kind: "dataFormat",
            detail: "'\(setting)' is a \(control.reading.role), which a step cannot set",
            remedy: "set a pop-up, a checkbox, a radio button or a field"))
    }
    Thread.sleep(forTimeInterval: 1.0)
    let after = try readDataFormatControls(in: window)
    let wanted = control.reading.role == kAXPopUpButtonRole ? readItemChoice(value).title : value
    guard let shown = after.first(where: { $0.reading.setting == setting }), shown.reading.value == wanted
    else {
        throw HelperFailure(problem: HelperProblem(
            kind: "dataFormat",
            detail: "'\(setting)' was set to '\(value)', and the section now reads: "
                + describeDataFormat(after),
            remedy: "spell the value as the section reads it, then rerun"))
    }
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
// Every error ScreenCaptureKit reports, the underlying ones included, so a log says why.
func describeError(_ error: Error) -> String {
    let error = error as NSError
    var parts = ["\(error.domain) \(error.code): \(error.localizedDescription)"]
    if let underlying = error.userInfo[NSUnderlyingErrorKey] as? Error {
        parts.append("underlying " + describeError(underlying))
    }
    for each in (error.userInfo[NSMultipleUnderlyingErrorsKey] as? [Error]) ?? [] {
        parts.append("underlying " + describeError(each))
    }
    return parts.joined(separator: "; ")
}

func captureWindowImage(id windowId: Int) -> (CGImage?, String, Bool) {
    var image: CGImage?
    var said = ""
    var streamFailed = false
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
            let state = "window \(windowId) on screen \(window.isOnScreen), frame \(window.frame), "
                + "layer \(window.windowLayer), owner \(window.owningApplication?.bundleIdentifier ?? "none"), "
                + "requested \(configuration.width)x\(configuration.height)"
            said = error.map { "\(describeError($0)); \(state)" } ?? state
            streamFailed = (error as NSError?).map {
                $0.domain == SCStreamErrorDomain && $0.code == streamStartFailedError
            } ?? false
            done.signal()
        }
    }
    done.wait()
    return (image, said, streamFailed)
}

func captureWindow(
    id windowId: Int, window: AXUIElement, crop: CGRect?, to path: String, pid: pid_t
) throws {
    var captured: CGImage?
    var said = ""
    var streamFailed = false
    // ScreenCaptureKit refuses a hidden app's window, measured 2026-10-29 on macOS 26.6.1,
    // so Numbers is shown for the capture alone and hidden again.
    let hidden = NSRunningApplication(processIdentifier: pid)?.isHidden ?? false
    if hidden { setNumbersHidden(pid: pid, false) }
    defer { if hidden { setNumbersHidden(pid: pid, true) } }
    // A window not yet drawn captures on a later try.
    for _ in 0..<windowAttempts {
        (captured, said, streamFailed) = captureWindowImage(id: windowId)
        if captured != nil { break }
        Thread.sleep(forTimeInterval: streamFailed ? streamRetryPauseSeconds : retryPauseSeconds)
    }
    let counts = countNumbersWindows(pid: pid)
    writeLog("captured \((path as NSString).lastPathComponent): \(captured != nil) (\(said)), "
        + "Numbers hidden before \(hidden), windows on screen \(counts.onScreen) of \(counts.all)")
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

// Hidden, Numbers stays out of the developer's way between captures, which show it.
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
        let tables = request.tables ?? []
        let sheets = (tables.map(\.sheet) + cells.map(\.sheet))
            .reduce(into: [String]()) { if !$0.contains($1) { $0.append($1) } }
        let textOnly = request.textOnly ?? false
        let captureCount = textOnly ? 0 : sheets.count + cells.count
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
            sheets: textOnly ? [] : sheets, textOnly: textOnly, numbers: numbers,
            result: &result)
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

// Opens one document, refusing it and saying why when Numbers crashes, refuses or warns.
func openDocument(
    _ documentPath: String, numbers: NSRunningApplication, result: inout HelperResult
) throws -> String {
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
    return documentId
}

func inspectDocument(
    documentPath: String, savedCopyPath: String, captureDirectory: String,
    cells: [CellAddress], tables: [TableAddress], sheets: [String], textOnly: Bool,
    numbers: NSRunningApplication, result: inout HelperResult
) throws {
    let documentId = try openDocument(documentPath, numbers: numbers, result: &result)
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
        // Any cell of the sheet brings it forward, and A1 exists in every table.
        let first = cells.first { $0.sheet == sheet }
            ?? tables.first { $0.sheet == sheet }.map { CellAddress(sheet: $0.sheet, table: $0.table, cell: "A1") }!
        try selectCell(first, documentId: documentId)
        let path = (captureDirectory as NSString).appendingPathComponent(
            formatCaptureName(["sheet", sheet]))
        // A capture that fails is recorded, and the readings that need none go on.
        do {
            try captureWindow(
                id: Int(windowId), window: window, crop: nil, to: path,
                pid: numbers.processIdentifier)
            result.sheetCaptures.append(SheetCapture(sheet: sheet, path: path))
        } catch let failure as HelperFailure {
            result.problems.append(failure.problem)
        }
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
        if textOnly {
            result.cells.append(reading)
            continue
        }
        try selectCell(address, documentId: documentId)
        try openCellTab(in: window)
        reading.dataFormat = try readDataFormat(in: window)
        let path = (captureDirectory as NSString).appendingPathComponent(
            formatCaptureName(["cell", address.sheet, address.table, address.cell]))
        do {
            try captureWindow(
                id: Int(windowId), window: window, crop: findDataFormatFrame(in: window),
                to: path, pid: numbers.processIdentifier)
            reading.inspectorCapture = path
        } catch let failure as HelperFailure {
            result.problems.append(failure.problem)
        }
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
            + "set grid to {}\n"
            + "repeat with r in rows of t\n"
            + "set end of names to name of cells of r\n"
            + "set kinds to {}\n"
            + "repeat with c in cells of r\n"
            + "set end of kinds to (format of c) as text\n"
            + "end repeat\n"
            + "set end of grid to {value of cells of r, formula of cells of r, kinds}\n"
            + "end repeat\n"
            + "return {row count of t, column count of t, names, grid}")
    let rows = facts.atIndex(3)
    let cellNames = (0..<(rows?.numberOfItems ?? 0)).map { row in
        let names = rows?.atIndex(row + 1)
        return (0..<(names?.numberOfItems ?? 0)).map { names?.atIndex($0 + 1)?.stringValue ?? "" }
    }
    let grid = facts.atIndex(4)
    let cellFacts = (0..<(grid?.numberOfItems ?? 0)).map { row -> [CellFact] in
        let columns = grid?.atIndex(row + 1)
        let values = columns?.atIndex(1), formulas = columns?.atIndex(2), kinds = columns?.atIndex(3)
        return (0..<(values?.numberOfItems ?? 0)).map { column in
            CellFact(
                value: values?.atIndex(column + 1).map(readCellValue) ?? CellValue(kind: "empty", text: ""),
                formula: formulas?.atIndex(column + 1).flatMap(readOptionalText),
                formatKind: kinds?.atIndex(column + 1)?.stringValue)
        }
    }
    return TableReading(
        address: address, rowCount: Int(facts.atIndex(1)?.int32Value ?? 0),
        columnCount: Int(facts.atIndex(2)?.int32Value ?? 0), cellNames: cellNames,
        cellFacts: cellFacts)
}

func selectCell(_ address: CellAddress, documentId: String) throws {
    let document = "document id \(quoteAppleScript(documentId))"
    _ = try runAppleScript(
        "set t to table \(quoteAppleScript(address.table)) of sheet \(quoteAppleScript(address.sheet)) of \(document)\n"
            + "set active sheet of \(document) to sheet \(quoteAppleScript(address.sheet)) of \(document)\n"
            + "set selection range of t to range \(quoteAppleScript(address.cell + ":" + address.cell)) of t")
    Thread.sleep(forTimeInterval: 0.5)
}

// MARK: Editing

// A menu bar lists its items directly, and every other item holds its own inside one AXMenu.
func listMenuItems(_ element: AXUIElement) -> [AXUIElement] {
    (readAttribute(element, kAXChildrenAttribute) as? [AXUIElement] ?? []).flatMap { child in
        readText(child, kAXRoleAttribute) == kAXMenuRole
            ? readAttribute(child, kAXChildrenAttribute) as? [AXUIElement] ?? [] : [child]
    }
}

func pressMenuItem(_ item: EditMenuItem, pid: pid_t) throws {
    guard let bar = readAttribute(AXUIElementCreateApplication(pid), kAXMenuBarAttribute) else {
        throw HelperFailure(problem: HelperProblem(
            kind: "menu", detail: "Numbers' menu bar was not reachable through Accessibility",
            remedy: "bring Numbers forward, then rerun"))
    }
    var element = bar as! AXUIElement
    for title in item.path {
        let items = listMenuItems(element)
        guard let found = items.first(where: { readText($0, kAXTitleAttribute) == title }) else {
            let titles = items.map { readText($0, kAXTitleAttribute) }.filter { !$0.isEmpty }
            throw HelperFailure(problem: HelperProblem(
                kind: "menu",
                detail: "no menu item '\(title)' on the way to \(item.path.joined(separator: " > ")), "
                    + "among: " + titles.joined(separator: ", "),
                remedy: "correct EditMenuItem.path in the helper, then rebuild it"))
        }
        element = found
    }
    guard readAttribute(element, kAXEnabledAttribute) as? Bool != false else {
        throw HelperFailure(problem: HelperProblem(
            kind: "menu", detail: "\(item.path.joined(separator: " > ")) is disabled",
            remedy: "check the selection the step before it makes"))
    }
    AXUIElementPerformAction(element, kAXPressAction as CFString)
    Thread.sleep(forTimeInterval: 1.0)
}

func formatRangeReference(_ step: EditStep, documentId: String) throws -> (table: String, range: String) {
    guard let sheet = step.sheet, let table = step.table, let range = step.range else {
        throw HelperFailure(problem: HelperProblem(
            kind: "request", detail: "a \(step.action.rawValue) step needs a sheet, a table and a range",
            remedy: "run the helper only through the golden confirmation"))
    }
    let document = "document id \(quoteAppleScript(documentId))"
    return (
        "table \(quoteAppleScript(table)) of sheet \(quoteAppleScript(sheet)) of \(document)",
        "range \(quoteAppleScript(range))"
    )
}

// Only letters then digits parse, so nothing else from a request reaches the script.
func readCellPosition(_ cell: String) -> (row: Int, column: Int)? {
    let letters = cell.prefix { $0.isASCII && $0.isUppercase }
    guard !letters.isEmpty, let row = Int(cell.dropFirst(letters.count)), row > 0 else { return nil }
    let column = letters.reduce(0) { $0 * 26 + Int($1.asciiValue! - 64) }
    return (row, column)
}

func selectRange(_ step: EditStep, documentId: String) throws {
    let (table, range) = try formatRangeReference(step, documentId: documentId)
    _ = try runAppleScript(
        "set t to \(table)\n"
            + "set active sheet of document id \(quoteAppleScript(documentId)) to sheet "
            + "\(quoteAppleScript(step.sheet ?? "")) of document id \(quoteAppleScript(documentId))\n"
            + "set selection range of t to \(range) of t")
    Thread.sleep(forTimeInterval: 0.5)
}

func runEditStep(_ step: EditStep, documentId: String, numbers: NSRunningApplication) throws {
    let (_, window) = try findDocumentWindow(documentId: documentId, pid: numbers.processIdentifier)
    AXUIElementPerformAction(window, kAXRaiseAction as CFString)
    numbers.activate()
    Thread.sleep(forTimeInterval: 0.5)
    switch step.action {
    case .select:
        try selectRange(step, documentId: documentId)
    case .dataFormatSet:
        guard let setting = step.setting, let value = step.value else {
            throw HelperFailure(problem: HelperProblem(
                kind: "request", detail: "a dataFormatSet step needs a setting and a value",
                remedy: "run the helper only through the golden confirmation"))
        }
        try selectRange(step, documentId: documentId)
        try openCellTab(in: window)
        try setDataFormatControl(setting, to: value, in: window)
    case .customFormatEdit:
        guard let part = step.setting else {
            throw HelperFailure(problem: HelperProblem(
                kind: "request", detail: "a customFormatEdit step needs a setting",
                remedy: "name a part of the Create Custom Format dialog"))
        }
        if part == "Open" {
            try selectRange(step, documentId: documentId)
            try openCellTab(in: window)
            try openCustomFormat(in: window)
        } else {
            try editCustomFormat(part, value: step.value ?? "", in: window)
        }
    case .tableExtend:
        let (table, _) = try formatRangeReference(step, documentId: documentId)
        guard let (row, column) = step.range.flatMap(readCellPosition) else {
            throw HelperFailure(problem: HelperProblem(
                kind: "request", detail: "a tableExtend step needs one cell, such as I2",
                remedy: "name the last cell the table must reach"))
        }
        _ = try runAppleScript(
            "set t to \(table)\n"
                + "if row count of t < \(row) then set row count of t to \(row)\n"
                + "if column count of t < \(column) then set column count of t to \(column)")
    case .sheetAdd:
        // A new sheet holds a table with a header row and column, which a measurement has none of.
        guard let sheet = step.sheet else {
            throw HelperFailure(problem: HelperProblem(
                kind: "request", detail: "a sheetAdd step needs the new sheet's name",
                remedy: "name the sheet in the step's sheet"))
        }
        let document = "document id \(quoteAppleScript(documentId))"
        _ = try runAppleScript(
            "tell \(document) to set s to make new sheet with properties {name:\(quoteAppleScript(sheet))}\n"
                + "set t to table 1 of s\n"
                + "set header row count of t to 0\nset header column count of t to 0\nset footer row count of t to 0")
    case .tableAdd:
        guard let sheet = step.sheet, let table = step.table,
              let (row, column) = step.range.flatMap(readCellPosition) else {
            throw HelperFailure(problem: HelperProblem(
                kind: "request", detail: "a tableAdd step needs a sheet, a table and its last cell, such as B3",
                remedy: "name the sheet, the new table and the cell it must reach"))
        }
        let target = "sheet \(quoteAppleScript(sheet)) of document id \(quoteAppleScript(documentId))"
        _ = try runAppleScript(
            "tell \(target) to set t to make new table with properties {name:\(quoteAppleScript(table))}\n"
                + "set header row count of t to 0\nset header column count of t to 0\nset footer row count of t to 0\n"
                + "set row count of t to \(row)\nset column count of t to \(column)")
    case .menuPress:
        guard let item = step.menuItem else {
            throw HelperFailure(problem: HelperProblem(
                kind: "request", detail: "a menuPress step needs a menuItem",
                remedy: "run the helper only through the golden confirmation"))
        }
        try pressMenuItem(item, pid: numbers.processIdentifier)
    case .formatSet:
        let (table, range) = try formatRangeReference(step, documentId: documentId)
        guard let format = step.format else {
            throw HelperFailure(problem: HelperProblem(
                kind: "request", detail: "a formatSet step needs a format",
                remedy: "run the helper only through the golden confirmation"))
        }
        _ = try runAppleScript("set t to \(table)\nset format of \(range) of t to \(format.rawValue)")
    case .valueSet:
        // Numbers parses a value starting with "=" as a formula, storing it as typed.
        let (table, _) = try formatRangeReference(step, documentId: documentId)
        guard let value = step.value, let cell = step.range else {
            throw HelperFailure(problem: HelperProblem(
                kind: "request", detail: "a valueSet step needs a value and a single cell",
                remedy: "run the helper only through the golden confirmation"))
        }
        _ = try runAppleScript(
            "set t to \(table)\nset value of cell \(quoteAppleScript(cell)) of t to \(quoteAppleScript(value))")
    }
}

// Numbers stays in view, since a menu acts on the frontmost window and its selection.
func runDocumentEdit(_ request: HelperRequest) -> HelperResult {
    var result = HelperResult(sourceHash: readSourceHash(), operation: request.operation.rawValue)
    result.problems = findSessionProblems() + findGrantProblems()
    guard result.problems.isEmpty else { return result }
    do {
        let paths = try (request.documentPaths ?? []).map { try checkTemporaryPath($0, field: "documentPaths") }
        let savedCopyPath = try checkTemporaryPath(request.savedCopyPath, field: "savedCopyPath")
        let steps = request.steps ?? []
        guard !paths.isEmpty, steps.allSatisfy({ paths.indices.contains($0.document) }) else {
            throw HelperFailure(problem: HelperProblem(
                kind: "request", detail: "every step must name one of the documentPaths",
                remedy: "run the helper only through the golden confirmation"))
        }
        let (numbers, launched) = try launchNumbers()
        if launched { numbersLaunchedByRun = numbers }
        defer { quitNumbersLaunched(launched, numbers: numbers) }
        try checkAutomationPermission()
        try checkNoUnsavedDocuments()
        result.numbersVersion = try? runAppleScript("get version").stringValue
        var documentIds: [String] = []
        defer {
            for id in documentIds where kill(numbers.processIdentifier, 0) == 0 {
                _ = try? runAppleScript("close (document id \(quoteAppleScript(id))) saving no")
            }
        }
        for path in paths {
            documentIds.append(try openDocument(path, numbers: numbers, result: &result))
        }
        result.stepsDone = 0
        for step in steps {
            writeLog("step \(step.action.rawValue) in document \(step.document)")
            try runEditStep(step, documentId: documentIds[step.document], numbers: numbers)
            result.stepsDone = (result.stepsDone ?? 0) + 1
        }
        _ = try runAppleScript(
            "save document id \(quoteAppleScript(documentIds[0])) in (POSIX file \(quoteAppleScript(savedCopyPath)))")
        result.savedCopy = FileManager.default.fileExists(atPath: savedCopyPath)
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
    case .documentEdit:
        result = runDocumentEdit(request)
    }
    writeResult(result, to: request.resultPath)
}

guard CommandLine.arguments.count == 2 else {
    FileHandle.standardError.write(Data("usage: pybersdev-golden-confirm <request.json>\n".utf8))
    exit(2)
}
runRequest(at: CommandLine.arguments[1])
