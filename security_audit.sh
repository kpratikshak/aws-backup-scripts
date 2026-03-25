bash script to audit security logs
#!/bin/bash

# Check currently logged-in users
echo -e "\nCurrently logged-in users:"
w

# List running processes
echo -e "\nRunning processes:"
ps aux

# List open network connections
echo -e "\nOpen network connections:"
netstat -tulpn

# Scan for open ports
echo -e "\nScanning for open ports:"
nmap -sS localhost

# Check authentication logs for failed login attempts
echo -e "\nFailed login attempts:"
sudo grep "Failed password" /var/log/auth.log

echo "Security Audit Complete."
