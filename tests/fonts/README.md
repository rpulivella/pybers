# Fonts the tests choose from

Fira Sans 4.301, eleven of its fonts, from the OTF release in
[bBoxType/FiraSans](https://github.com/bBoxType/FiraSans), under the SIL Open Font License
in `fira-sans/OFL.txt`, which permits bundling it. A test resolves a font by typeface,
weight and slant against these files rather than the machine's, so it runs anywhere.
Hair and Thin share weight 100, which is why both are here: weight and slant alone cannot
choose between them.
