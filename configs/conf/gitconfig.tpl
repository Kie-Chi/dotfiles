[user]
	name = {{.vars.username}}
	email = {{.vars.email}}
[color]
	ui = true
[alias]
	plog = "log --graph --date=format:'%Y-%m-%d %H:%M:%S %A' --pretty=format:'%C(bold blue)commit: %C(bold red)%h %C(#00A89A)%d %n%C(bold blue)parent commit: %C(bold red)%p %n%C(bold blue)title: %C(#A477DB)%s  %n%C(bold blue)content: %C(#A477DB)%b %n%C(bold blue)author: %C(#1B92D6)%an <%ae> %n%C(bold blue)date: %C(#1B92D6)%ad %C(#4EAB00)(%ar) %n%n'"
	st = status
	ci = commit
	co = checkout
	unstage = reset HEAD
	dif = diff
	ust = unstage
	br = branch
	lg = log --color --graph --pretty=format:'%Cred%h%Creset -%C(yellow)%d%Creset %s %Cgreen(%cr) %C(bold blue)<%an>%Creset' --abbrev-commit
	sw = show --color --compact-summary --pretty=format:'%Cred%h%Creset -%C(yellow)%d%Creset %s %Cgreen(%cr) %C(bold blue)<%an>%Creset' --abbrev-commit
	rt = remote
