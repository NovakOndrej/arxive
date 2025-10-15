import qrcode

url = "https://arxivbutler.com/"
img = qrcode.make(url)
img.save("arxivbutler_qr.png")
print("QR code saved as arxivbutler_qr.png")
