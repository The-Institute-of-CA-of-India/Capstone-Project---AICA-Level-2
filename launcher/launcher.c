/* Investor Manager launcher.
 * First run (or new version): unpacks the bundled Python runtime, libraries,
 * OCR engine and app into %LOCALAPPDATA%\ContractNoteManager using the
 * setup script in "App Files". Then starts the app with no console window.
 * Data stays next to this exe in the "Data" folder. */
#include <windows.h>
#include <shlobj.h>
#include <wchar.h>

#ifndef APPVER
#define APPVER L"v1.2"
#endif

static wchar_t exeDir[MAX_PATH], base[MAX_PATH], payload[MAX_PATH];

static int file_exists(const wchar_t *p) {
    DWORD a = GetFileAttributesW(p);
    return a != INVALID_FILE_ATTRIBUTES && !(a & FILE_ATTRIBUTE_DIRECTORY);
}

static DWORD run_wait(wchar_t *cmd, int show) {
    STARTUPINFOW si = { sizeof(si) }; PROCESS_INFORMATION pi;
    si.dwFlags = STARTF_USESHOWWINDOW; si.wShowWindow = show ? SW_SHOWNORMAL : SW_HIDE;
    if (!CreateProcessW(NULL, cmd, NULL, NULL, FALSE, show ? CREATE_NEW_CONSOLE : CREATE_NO_WINDOW,
                        NULL, NULL, &si, &pi)) return 9999;
    WaitForSingleObject(pi.hProcess, INFINITE);
    DWORD code = 1; GetExitCodeProcess(pi.hProcess, &code);
    CloseHandle(pi.hThread); CloseHandle(pi.hProcess);
    return code;
}

int WINAPI wWinMain(HINSTANCE hi, HINSTANCE hp, PWSTR args, int show) {
    wchar_t tmp[MAX_PATH * 4], pyw[MAX_PATH], local[MAX_PATH];
    GetModuleFileNameW(NULL, exeDir, MAX_PATH);
    wchar_t *slash = wcsrchr(exeDir, L'\\'); if (slash) *slash = 0;
    if (FAILED(SHGetFolderPathW(NULL, CSIDL_LOCAL_APPDATA, NULL, 0, local))) {
        MessageBoxW(NULL, L"Could not find the local AppData folder.", L"Investor Manager", MB_ICONERROR);
        return 1;
    }
    swprintf(base, MAX_PATH, L"%ls\\ContractNoteManager", local);
    swprintf(payload, MAX_PATH, L"%ls\\App Files", exeDir);
    swprintf(pyw, MAX_PATH, L"%ls\\runtime\\python\\pythonw.exe", base);

    wchar_t appzip[MAX_PATH], runpy[MAX_PATH], tess[MAX_PATH];
    swprintf(appzip, MAX_PATH, L"%ls\\app_%ls.zip", payload, APPVER);
    swprintf(runpy, MAX_PATH, L"%ls\\app\\%ls\\run.py", base, APPVER);
    swprintf(tess, MAX_PATH, L"%ls\\tesseract\\tesseract.exe", base);
    if (!file_exists(appzip) && !file_exists(runpy)) {
        MessageBoxW(NULL, L"This version's program file (App Files\\app_" APPVER L".zip) is missing.\n"
                          L"Keep the exe and the \"App Files\" folder together.", L"Investor Manager " APPVER,
                    MB_ICONERROR);
        return 1;
    }
    if (!file_exists(pyw) || !file_exists(runpy) || !file_exists(tess)) {
        swprintf(tmp, MAX_PATH * 4, L"cmd.exe /c \"\"%ls\\setup.cmd\" \"%ls\" \"%ls\" %ls\"", payload, payload, base, APPVER);
        DWORD rc = run_wait(tmp, 1);
        if (rc != 0 || !file_exists(pyw) || !file_exists(runpy)) {
            MessageBoxW(NULL, L"Setup did not complete.\nPlease run it again; if it still fails, "
                              L"check free disk space on drive C:.", L"Investor Manager " APPVER, MB_ICONERROR);
            return 1;
        }
    }

    swprintf(tmp, MAX_PATH, L"%ls\\Data", exeDir);               SetEnvironmentVariableW(L"CNM_DATA", tmp);
    CreateDirectoryW(tmp, NULL);
    SetEnvironmentVariableW(L"CNM_PROJECT", exeDir);
    swprintf(tmp, MAX_PATH, L"%ls\\Data\\.app", exeDir);          SetEnvironmentVariableW(L"NICEGUI_STORAGE_PATH", tmp);
    swprintf(tmp, MAX_PATH, L"%ls\\tesseract\\tesseract.exe", base); SetEnvironmentVariableW(L"CNM_TESSERACT", tmp);
    swprintf(tmp, MAX_PATH, L"%ls\\tesseract\\tessdata", base);  SetEnvironmentVariableW(L"TESSDATA_PREFIX", tmp);
    SetEnvironmentVariableW(L"CNM_VERSION", APPVER);

    wchar_t appdir[MAX_PATH]; swprintf(appdir, MAX_PATH, L"%ls\\app\\%ls", base, APPVER);
    swprintf(tmp, MAX_PATH * 4, L"\"%ls\" \"%ls\\run.py\"", pyw, appdir);
    STARTUPINFOW si = { sizeof(si) }; PROCESS_INFORMATION pi;
    if (!CreateProcessW(NULL, tmp, NULL, NULL, FALSE, CREATE_NO_WINDOW, NULL, appdir, &si, &pi)) {
        MessageBoxW(NULL, L"Could not start the application.", L"Investor Manager", MB_ICONERROR);
        return 1;
    }
    CloseHandle(pi.hThread); CloseHandle(pi.hProcess);
    return 0;
}
