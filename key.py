import base64

password = input("Enter Message Central API key: ")
encoded = base64.b64encode(password.encode()).decode()
print(encoded)