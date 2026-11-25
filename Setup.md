# LegalChef Work Organiser

## Start the office server

1. Copy **LegalChef Work Organiser.exe** to a writable folder on the Windows x64 machine that will act as the server. Run it under a dedicated Windows account or an account with access to that folder.
2. Double-click the executable and leave its console window open. On the server, open **http://127.0.0.1:8765** and create the super admin account. Save these credentials in your password manager.
3. In Windows Command Prompt on the server, run `ipconfig` and find the IPv4 address of the active Ethernet or Wi-Fi adapter. On each of the five office computers, open **http://SERVER-IP:8765**, replacing SERVER-IP with that address. For example, use **http://192.168.1.20:8765** if that is the server's IP. The executable only needs to run on the server.
4. If the other computers cannot connect, have your Windows administrator allow inbound TCP port **8765** for the private office network, ideally scoped to the office subnet or the five workstations' IP addresses. Keep the server on and avoid router port forwarding. A DHCP reservation helps keep the bookmarked address stable.

The built-in listener uses HTTP. Keep it on a trusted office network. Before using it with real client records, have your IT administrator put it behind an HTTPS reverse proxy if credentials or records would cross an untrusted network. After first-time loopback setup, run the app with `--host 127.0.0.1 --secure-cookie` for a reverse proxy on the same server and have staff use the proxy's HTTPS URL.

If LegalChef is already installed, stop the running copy, replace only the executable in the same folder, and restart it. Keep the **LegalChef Data** folder in place.

## Use the organiser

- **Clients** lets the super admin select as many applicable services as needed. Use **Other** for work outside Income tax, GST, Appeals and Bookkeeping. The same client appears in every selected service section.
- Under **Staff & super admins**, select **Add super admin** to create a second super admin with a separate username and temporary password. They choose a new password on first sign-in. Both super admins have access to all clients, tasks, accounts and backups.
- Under **Staff & super admins**, create a separate username and temporary password for each staff member. Staff choose a new password when they first sign in. The super admin can reset passwords and deactivate or reactivate accounts.
- From **Overview** or a service section, choose **New task**. Choose the client and service, add instructions, assign staff, and optionally set a due date. Leaving the staff field blank creates an unassigned task.
- Staff can open their assigned tasks, record progress, select **Running**, **Ready for review** or **Completed**, and raise a red flag for urgent review. The super admin can review, reassign or reopen tasks. Each task displays its activity history.
- Select a dashboard total to filter the task list. **Overdue** includes unfinished tasks with a due date before today. **Flagged** shows unfinished tasks with a red flag. Dates follow the server's calendar.

## Back up and restore

The database lives in the **LegalChef Data** folder alongside the executable by default. Give only the Windows server account and authorised administrators access to that folder. The super admin can use **Download backup** for a consistent snapshot while people are working. Store snapshots in a protected location.

To restore, stop LegalChef. Move the existing **LegalChef Data** folder to a safe location as a rollback copy. Create a new **LegalChef Data** folder and copy the downloaded snapshot into it as **legalchef.sqlite3**. Restart LegalChef and sign in with an account from the restored snapshot.

## Run the Python source

The source includes the logo and the entire interface. In a Python 3.12 environment, install Flask and Waitress, then run the script.

```powershell
py -3.12 -m pip install Flask==3.1.3 waitress==3.0.2
py -3.12 legalchef.py
```

Both the Python script and the executable accept `--host`, `--port`, `--data-dir`, and `--secure-cookie`. Run one server instance per database.
