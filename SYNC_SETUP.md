# Crux sync setup (desktop <-> AnkiDroid)

Crux uses **Anki's own sync** (the shared Rust engine), not a third-party
service. This document sets up a **self-hosted sync server** on your machine so
the desktop app and the phone app sync the same collection with no AnkiWeb
account. It also gives the exact steps for the section 7b sync/conflict test.

## 1. Start the server

With the desktop app closed (so it isn't holding the collection), run:

```powershell
powershell -ExecutionPolicy Bypass -File tools\crux_sync_server.ps1
```

It prints the URLs to use and starts listening on port 8080. Credentials are
`crux` / `crux` (change `SYNC_USER1` in the script to something else if you like).
Data is stored under `sync_server_data\` (gitignored).

Leave this window running while you sync.

## 2. Point the desktop app at it

Tools > Preferences > Syncing > **Self-hosted sync server**, set:

```
http://127.0.0.1:8080/
```

Then Sync (press `Y` or the sync button) and log in as `crux` / `crux`. On the
first sync, choose **Upload to server** so the server has your collection.

## 3. Point AnkiDroid at it

AnkiDroid > Settings > Advanced > **Custom sync server**, set both the sync URL
and the media sync URL to:

- **Emulator:** `http://10.0.2.2:8080/`  (10.0.2.2 is the host machine from inside
  the Android emulator)
- **Real phone on the same wifi:** `http://<your-machine-ip>:8080/`  (the script
  prints the IP)

Then log in as `crux` / `crux` and sync. Choose **Download from server** on the
first sync so the phone matches the desktop.

## 4. The 7b sync + conflict test

Goal: 20 reviews across two devices, none lost or double-counted, plus a clean
conflict rule.

1. Make sure both apps are synced to the same state first.
2. Put **both** devices offline (desktop: stay off the server; phone: airplane
   mode / emulator network off).
3. On the **phone**, review **10** cards. On the **desktop**, review **10
   different** cards.
4. Reconnect both and sync (phone first, then desktop, or the reverse).
5. Confirm all **20** reviews are present on both devices, counted once. Check the
   review count / revlog on each side.
6. **Conflict case:** offline, review the **same** card on both devices with
   different answers. Sync both. Anki's merge resolves by the review log; the
   later-timestamped review wins and no review is dropped. Record which side won
   and that no data was lost.

Anki's sync is offline-first and its revlog merge is the documented conflict
rule, so you are reusing the shared engine's guarantees rather than inventing a
new merge.

## Notes

- The server binds to `0.0.0.0`, so a real phone on the same network can reach it
  at the printed IP. If it can't connect, allow port 8080 through the Windows
  firewall for private networks.
- Your Crux data (exam attempts and tunables) lives in the collection config,
  which syncs too, so readiness state follows you across devices.
