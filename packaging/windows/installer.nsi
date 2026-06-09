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
;
; ── VERSION — update these three lines for every release ─────────────────────
!define APP_VERSION     "0.2.0"
!define VER_MAJOR       "0"
!define VER_MINOR       "2"
; ─────────────────────────────────────────────────────────────────────────────

!define APP_NAME        "Tiki-Taka PAY DWH"
!define APP_EXE         "TikiTakaPAYDWH.exe"
!define APP_PUBLISHER   "Tikitaka"
!define APP_URL         "https://tikitaka.lv"
!define INSTALL_DIR     "$LOCALAPPDATA\Programs\TikiTakaPAYDWH"
!define UNINSTALL_KEY   "Software\Microsoft\Windows\CurrentVersion\Uninstall\TikiTakaPAYDWH"
!define DIST_DIR        "..\..\dist\TikiTakaPAYDWH"

; Data directory is managed entirely by the app (platformdirs) and must never
; be touched by the installer or uninstaller — it holds the warehouse DB,
; all raw JSON files, and the user's credentials.
; Data dir (read-only reference for documentation):
;   %LOCALAPPDATA%\TikiTakaPAYDWH  (no trailing backslash — avoids NSIS line-continuation)

Name            "${APP_NAME} ${APP_VERSION}"
OutFile         "TikiTakaPAYDWH-Setup-x64.exe"
InstallDir      "${INSTALL_DIR}"
; On upgrade, re-use the previously chosen install location
InstallDirRegKey HKCU "${UNINSTALL_KEY}" "InstallLocation"
RequestExecutionLevel user
SetCompressor   /SOLID lzma
Unicode         True

; Modern UI
!include "MUI2.nsh"
!include "FileFunc.nsh"
!include "LogicLib.nsh"

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

; ── Close running instance ────────────────────────────────────────────────────
; If the app is running its Python DLLs will be file-locked and the installer
; will fail mid-copy.  Ask the user to close it (or force-close for them).
Function CloseRunningApp
    ; tasklist /FI filters by image name; if the process exists the output
    ; contains the exe name, otherwise it contains only the "no tasks" notice.
    nsExec::ExecToStack 'tasklist /FI "IMAGENAME eq ${APP_EXE}" /NH /FO CSV'
    Pop $0   ; exit code
    Pop $1   ; stdout

    ${If} $1 != ""
    ${AndIf} $1 != "INFO: No tasks are running which match the specified criteria."
        MessageBox MB_OKCANCEL|MB_ICONEXCLAMATION \
            "${APP_NAME} is currently open.$\n$\nClick OK to close it automatically and continue, or Cancel to close it yourself first." \
            IDOK do_kill
        Abort   ; user chose Cancel
        do_kill:
        nsExec::ExecToLog 'taskkill /F /IM ${APP_EXE}'
        Sleep 2000   ; give the OS time to release file locks
    ${EndIf}
FunctionEnd

; ── Install ──────────────────────────────────────────────────────────────────
Section "MainSection" SEC01
    ; Must be first — DLLs are locked while the process runs
    Call CloseRunningApp

    ; On upgrade, wipe the previous version's files first — PyInstaller onedir
    ; layouts change between releases and stale DLLs/modules break the app.
    ; Guarded by the uninstaller's presence so a custom $INSTDIR that points
    ; at a shared folder is never wiped.  User data lives elsewhere
    ; (%LOCALAPPDATA%\TikiTakaPAYDWH) and is untouched.
    ${If} ${FileExists} "$INSTDIR\Uninstall.exe"
        RMDir /r "$INSTDIR"
    ${EndIf}

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
    ; Standard version fields used by Windows Update / patch managers
    WriteRegDWORD HKCU "${UNINSTALL_KEY}" "VersionMajor"     "${VER_MAJOR}"
    WriteRegDWORD HKCU "${UNINSTALL_KEY}" "VersionMinor"     "${VER_MINOR}"

    ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
    IntFmt $0 "0x%08X" $0
    WriteRegDWORD HKCU "${UNINSTALL_KEY}" "EstimatedSize" "$0"

    WriteUninstaller "$INSTDIR\Uninstall.exe"
SectionEnd

; ── Uninstall ────────────────────────────────────────────────────────────────
; NOTE: the data directory (%LOCALAPPDATA%\TikiTakaPAYDWH) is intentionally
; NOT removed here — it contains the warehouse database and all raw data.
; The user can delete it manually if they want a full clean removal.
Section "Uninstall"
    Call un.CloseRunningApp
    RMDir /r "$INSTDIR"
    Delete   "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk"
    RMDir    "$SMPROGRAMS\${APP_NAME}"
    Delete   "$DESKTOP\${APP_NAME}.lnk"
    DeleteRegKey HKCU "${UNINSTALL_KEY}"
SectionEnd

Function un.CloseRunningApp
    nsExec::ExecToStack 'tasklist /FI "IMAGENAME eq ${APP_EXE}" /NH /FO CSV'
    Pop $0
    Pop $1
    ${If} $1 != ""
    ${AndIf} $1 != "INFO: No tasks are running which match the specified criteria."
        nsExec::ExecToLog 'taskkill /F /IM ${APP_EXE}'
        Sleep 1500
    ${EndIf}
FunctionEnd
