#!/bin/bash

LOG_DIR="/var/log/process_monitor"
LOG_FILE="$LOG_DIR/process_mon.log"

create_logs() {

    mkdir -p "$LOG_DIR" || {
        echo "Failed to create log directory"
        exit 1
    }

    touch "$LOG_FILE" || {
        echo "Failed to create log file"
        exit 1
    }
}

create_logs

read cpu_pid cpu_name cpu_val <<< $(ps -eo pid,comm,%cpu --sort=-%cpu | awk 'NR==2{print $1,$2,$3}')
read mem_pid mem_name mem_val <<< $(ps -eo pid,comm,%mem --sort=-%mem | awk 'NR==2{print $1,$2,$3}')

timestamp=$(date +"%Y-%m-%dT%H:%M:%S")

cat <<EOF >> "$LOG_FILE"
{
"time":"$timestamp",
"top_cpu":{"pid":$cpu_pid,"name":"$cpu_name","cpu_percent":$cpu_val},
"top_ram":{"pid":$mem_pid,"name":"$mem_name","mem_percent":$mem_val}
}
EOF
