on run argv
	if (count of argv) < 3 then error "Usage: send_outlook_report.applescript <to_email> <subject> <body>"

	set recipientEmail to item 1 of argv
	set messageSubject to item 2 of argv
	set messageBody to item 3 of argv

	tell application "Microsoft Outlook"
		set outgoingMessage to make new outgoing message with properties {subject:messageSubject, content:messageBody}
		tell outgoingMessage
			make new recipient at end of to recipients with properties {email address:{address:recipientEmail}}
			send
		end tell
	end tell
end run
