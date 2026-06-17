import monobank

client = monobank.Client(token="uX7QPkC7i3H8APuNtKd_KVYS3Wl7_y2b5aEtOkcdWSx0")
info = client.get_client_info()

for jar in info.get("jars", []):
    print("title:", jar.get("title"))
    print("id:", jar.get("id"))
    print("sendId:", jar.get("sendId"))
    print("balance:", jar.get("balance"))
    print("---")