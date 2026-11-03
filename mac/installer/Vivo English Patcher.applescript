-- Vivo English Patcher: double-click installer for the macOS English patch.
-- mac/build_dmg.sh compiles this into an app and puts patch_vivo_mac.py and
-- the translation data in Contents/Resources/patcher (same layout as the
-- repository: data files at the top, the script in mac/).

property appTitle : "Vivo English Patcher"

on run
	set patcher to (POSIX path of (path to me)) & "Contents/Resources/patcher/mac/patch_vivo_mac.py"
	set py to findPython()
	if py is "" then
		display dialog "Python 3 is needed to apply the patch." & return & return & "Install Apple's Command Line Tools (free), then open this installer again." buttons {"Cancel", "Install"} default button "Install" cancel button "Cancel" with title appTitle with icon caution
		do shell script "xcode-select --install > /dev/null 2>&1 &"
		return
	end if

	set choice to button returned of (display dialog "Translate vivo PC Suite (China version) to English." & return & return & "vivo PC Suite will be closed and reopened. Your original files are backed up first, and Restore Original puts them back." buttons {"Cancel", "Restore Original", "Apply English Patch"} default button "Apply English Patch" cancel button "Cancel" with title appTitle with icon note)
	if choice is "Apply English Patch" then
		set args to "--yes"
	else
		set args to "--restore --yes"
	end if

	set progress total steps to -1
	set progress description to choice
	set progress additional description to "Starting..."
	set {rc, out} to runPatcher(py, patcher, args)

	if rc is 0 then
		if choice is "Apply English Patch" then
			set msg to "Done. vivo PC Suite is now in English."
		else
			set msg to "Done. vivo PC Suite is back to the original version."
		end if
		display dialog msg buttons {"OK"} default button "OK" with title appTitle with icon note
	else if out contains "App Management" then
		display dialog "macOS blocked the installer from changing vivo PC Suite." & return & return & "In System Settings > Privacy & Security > App Management, turn on " & appTitle & ", then open the installer again." buttons {"Cancel", "Open System Settings"} default button "Open System Settings" cancel button "Cancel" with title appTitle with icon caution
		do shell script "open 'x-apple.systempreferences:com.apple.preference.security?Privacy_AppBundles'"
	else
		display dialog "The patch did not complete:" & return & return & lastLines(out, 8) buttons {"OK"} default button "OK" with title appTitle with icon stop
	end if
end run

-- First Python 3.8+ found. /usr/bin/python3 is only a stub until the
-- Command Line Tools are installed, so it is tried only when they are.
on findPython()
	set candidates to {"/opt/homebrew/bin/python3", "/usr/local/bin/python3", "/Library/Frameworks/Python.framework/Versions/Current/bin/python3"}
	try
		do shell script "xcode-select -p"
		set end of candidates to "/usr/bin/python3"
	end try
	repeat with p in candidates
		try
			do shell script quoted form of (contents of p) & " -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)'"
			return contents of p
		end try
	end repeat
	return ""
end findPython

-- Run the patcher in the background and show its "==> step" lines as progress.
-- Returns {exit code, full output}.
on runPatcher(py, patcher, args)
	set logFile to do shell script "mktemp -t vivo-english-patch"
	set rcFile to logFile & ".rc"
	do shell script "(" & quoted form of py & " -I " & quoted form of patcher & " " & args & " > " & quoted form of logFile & " 2>&1; echo $? > " & quoted form of rcFile & ") > /dev/null 2>&1 &"
	repeat
		delay 0.5
		try
			set rc to (do shell script "cat " & quoted form of rcFile) as integer
			exit repeat
		end try
		set stepLine to do shell script "grep '^==> ' " & quoted form of logFile & " | tail -n 1 | cut -c 5-"
		if stepLine is not "" then
			try
				set progress additional description to stepLine
			end try
		end if
	end repeat
	set out to do shell script "cat " & quoted form of logFile
	do shell script "rm -f " & quoted form of logFile & " " & quoted form of rcFile
	return {rc, out}
end runPatcher

on lastLines(t, n)
	set ps to paragraphs of t
	set k to count of ps
	if k > n then set ps to items (k - n + 1) thru k of ps
	set AppleScript's text item delimiters to linefeed
	set s to ps as text
	set AppleScript's text item delimiters to ""
	return s
end lastLines
