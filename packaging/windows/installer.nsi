; Tiki-Taka PAY DWH — Windows NSIS Installer
;
; Requirements:
;   - NSIS >= 3.09  (https://nsis.sourceforge.io)
;   - makensis.exe on PATH
;
; Build:
;   makensis packaging\windows\installer.nsi
;
; Output: packaging\windows\TikiTakaPAYDWH-Setup-x64.exe

!define APP_NAME        "Tiki-Taka PAY DWH"
!define APP_EXE         "TikiTakaPAYDWH.exe"
!define APP_VERSION     "0.1.0"
!define APP_PUBLISHER   "Tikitaka"
!define APP_URL         "https://tikitaka.lv"
!define INSTALL_DIR     "$LOCALAPPDATA\Programs\TikiTakaPAYDWH"
!define UNINSTALL_KEY   "Software\Microsoft\Windows\CurrentVersion\Uninstall\TikiTakaPAYDWH"
!define DIST_DIR        "..\..\dist\TikiTakaPAYDWH"

Name            "${APP_NAME} ${APP_VERSION}"
OutFile         "TikiTakaPAYDWH-Setup-x64.exe"
InstallDir      "${INSTALL_DIR}"
InstallDirRegKey HKCU "${UNINSTALL_KEY}" "InstallLocation"
RequestExecutionLevel user
SetCompressor   /SOLID lzma
Unicode         True

; Modern UI
!include "MUI2.nsh"
!include "FileFunc.nsh"

!define MUI_ABORTWARNING
!if /FileExists "icon.ico"
!define MUI_ICON   "icon.ico"
!define MUI_UNICON "icon.ico"
!endif

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"
!insertmacro MUI_LANGUAGE "Latvian"

; ── Install ──────────────────────────────────────────────────────────────────
Section "MainSection" SEC01
    SetOutPath "$INSTDIR"
    File /r "${DIST_DIR}\*.*"

    ; Start Menu shortcut
    CreateDirectory "$SMPROGRAMS\${APP_NAME}"
    CreateShortcut  "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" \
                    "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}" 0

    ; Desktop shortcut
    CreateShortcut  "$DESKTOP\${APP_NAME}.lnk" \
                    "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}" 0

    ; Registry: Add/Remove Programs entry
    WriteRegStr   HKCU "${UNINSTALL_KEY}" "DisplayName"      "${APP_NAME}"
    WriteRegStr   HKCU "${UNINSTALL_KEY}" "DisplayVersion"   "${APP_VERSION}"
    WriteRegStr   HKCU "${UNINSTALL_KEY}" "Publisher"        "${APP_PUBLISHER}"
    WriteRegStr   HKCU "${UNINSTALL_KEY}" "URLInfoAbout"     "${APP_URL}"
    WriteRegStr   HKCU "${UNINSTALL_KEY}" "InstallLocation"  "$INSTDIR"
    WriteRegStr   HKCU "${UNINSTALL_KEY}" "UninstallString"  "$INSTDIR\Uninstall.exe"
    WriteRegDWORD HKCU "${UNINSTALL_KEY}" "NoModify"         1
    WriteRegDWORD HKCU "${UNINSTALL_KEY}" "NoRepair"         1

    ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
    IntFmt $0 "0x%08X" $0
    WriteRegDWORD HKCU "${UNINSTALL_KEY}" "EstimatedSize" "$0"

    WriteUninstaller "$INSTDIR\Uninstall.exe"
SectionEnd

; ── Uninstall ────────────────────────────────────────────────────────────────
Section "Uninstall"
    RMDir /r "$INSTDIR"
    Delete   "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk"
    RMDir    "$SMPROGRAMS\${APP_NAME}"
    Delete   "$DESKTOP\${APP_NAME}.lnk"
    DeleteRegKey HKCU "${UNINSTALL_KEY}"
SectionEnd
