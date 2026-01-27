with open('grantmatchproject/settings.py', 'r') as f:
    content = f.read()

old_host = "'HOST': '127.0.0.1',"
new_host = "'HOST': '35.198.216.10',"

content = content.replace(old_host, new_host)

with open('grantmatchproject/settings.py', 'w') as f:
    f.write(content)

print("Updated Cloud SQL host to public IP")
