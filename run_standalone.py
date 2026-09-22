import os
import socket
import threading
import webbrowser

from sahan_fleet import create_app

URL = "http://localhost:5000"
PORT = 5000


def _port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return False
        except OSError:
            return True


def _open_browser():
    threading.Timer(1.6, lambda: webbrowser.open(URL)).start()


def main():
    if _port_in_use(PORT):
        webbrowser.open(URL)
        return
    app = create_app()
    app.config["SECRET_KEY"] = os.urandom(24).hex()
    _open_browser()
    app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()