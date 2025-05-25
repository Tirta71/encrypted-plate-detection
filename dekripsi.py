import base64
import os
from tkinter import (
    Tk, Label, Entry, Button, Text, messagebox, filedialog,
    StringVar, OptionMenu, Canvas, Frame, Scrollbar
)
from PIL import Image, ImageTk
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from io import BytesIO

# === Kunci statik ===
key_b64 = "kKgTWK1FuLFlHrxRX8xlE7e9IYvqqMaI8CyZGhmmu6c="
key = base64.b64decode(key_b64)

# === GUI Setup ===
root = Tk()
root.title("Perbandingan Gambar: Sebelum & Setelah Dekripsi")
root.geometry("1000x900")

# === Scrollable Frame Setup ===
main_canvas = Canvas(root)
scroll_y = Scrollbar(root, orient="vertical", command=main_canvas.yview)
main_canvas.configure(yscrollcommand=scroll_y.set)

scroll_y.pack(side="right", fill="y")
main_canvas.pack(side="left", fill="both", expand=True)

# === Wrapper Frame untuk Centering
wrapper_frame = Frame(main_canvas)
main_canvas.create_window((0, 0), window=wrapper_frame, anchor="n", width=980)

wrapper_frame.bind(
    "<Configure>",
    lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all"))
)

# === Frame Isi (Scroll Frame) Centered Responsif
center_holder = Frame(wrapper_frame)
center_holder.grid(row=0, column=0, sticky="nsew", pady=20)

# Buat kolom 0 di wrapper_frame berkembang mengikuti ukuran jendela
wrapper_frame.grid_columnconfigure(0, weight=1)
wrapper_frame.grid_rowconfigure(0, weight=1)

# Buat frame konten (scroll_frame) diposisikan di tengah secara horizontal
scroll_frame = Frame(center_holder)
scroll_frame.pack(anchor="center")



# === Variabel UI ===
mode_var = StringVar()
mode_var.set("Teks")
original_img_tk = None

info_before = Label(scroll_frame, text="", fg="blue")
info_after = Label(scroll_frame, text="", fg="green")
size_before = Label(scroll_frame, text="", fg="blue")
size_after = Label(scroll_frame, text="", fg="green")

# === Fungsi: Load Gambar Asli ===
def load_original_image():
    global original_img_tk
    file_path = filedialog.askopenfilename(title="Pilih Gambar Asli", filetypes=[("Image Files", "*.jpg *.png")])
    if not file_path:
        return
    img = Image.open(file_path)
    img.thumbnail((400, 300))
    original_img_tk = ImageTk.PhotoImage(img)
    canvas_before.create_image(200, 150, image=original_img_tk)
    canvas_before.image = original_img_tk

    info_before.config(
        text=f"Gambar Asli - Ukuran: {img.width}x{img.height} | Format: {img.format or 'N/A'} | Mode: {img.mode}"
    )
    file_size = os.path.getsize(file_path) / 1024
    size_before.config(text=f"Ukuran File Asli: {file_size:.2f} KB")
    messagebox.showinfo("Berhasil", "Gambar asli berhasil dimuat.")

# === Fungsi: Dekripsi ===
def decrypt():
    try:
        nonce_b64 = entry_nonce.get().strip()
        nonce = base64.b64decode(nonce_b64)
        chacha = ChaCha20Poly1305(key)

        if mode_var.get() == "Teks":
            ciphertext_b64 = entry_cipher.get("1.0", "end-1c").strip()
            ciphertext = base64.b64decode(ciphertext_b64)
            plaintext = chacha.decrypt(nonce, ciphertext, None)
            output_text.delete("1.0", "end")
            output_text.insert("end", plaintext.decode())
            messagebox.showinfo("Sukses", "Teks berhasil didekripsi.")

        elif mode_var.get() == "Gambar":
            file_path = filedialog.askopenfilename(title="Pilih file .enc", filetypes=[("Encrypted Files", "*.enc")])
            if not file_path:
                return

            file_size_kb = os.path.getsize(file_path) / 1024
            size_after.config(text=f"Ukuran File .enc: {file_size_kb:.2f} KB")

            with open(file_path, "rb") as f:
                ciphertext = f.read()

            decrypted_data = chacha.decrypt(nonce, ciphertext, None)
            image_stream = BytesIO(decrypted_data)
            img = Image.open(image_stream)
            img.thumbnail((400, 300))
            decrypted_img_tk = ImageTk.PhotoImage(img)

            canvas_after.create_image(200, 150, image=decrypted_img_tk)
            canvas_after.image = decrypted_img_tk

            info_after.config(
                text=f"Hasil Dekripsi - Ukuran: {img.width}x{img.height} | Format: {img.format or 'N/A'} | Mode: {img.mode}"
            )

            messagebox.showinfo("Sukses", "Gambar berhasil didekripsi dan ditampilkan.")
    except Exception as e:
        messagebox.showerror("Gagal", f"Gagal mendekripsi:\n{e}")

# === Fungsi: Reset Semua ===
def reset_all():
    entry_nonce.delete(0, 'end')
    entry_cipher.delete("1.0", "end")
    output_text.delete("1.0", "end")
    canvas_before.delete("all")
    canvas_after.delete("all")
    info_before.config(text="")
    info_after.config(text="")
    size_before.config(text="")
    size_after.config(text="")

# === UI Layout ===
Label(scroll_frame, text="Pilih Mode Dekripsi:").pack(pady=(10, 0))
OptionMenu(scroll_frame, mode_var, "Teks", "Gambar").pack()

Label(scroll_frame, text="Nonce (Base64):").pack()
entry_nonce = Entry(scroll_frame, width=100)
entry_nonce.pack(pady=5)

Label(scroll_frame, text="Ciphertext (Base64) [Untuk Teks Saja]:").pack()
entry_cipher = Text(scroll_frame, height=10, width=100)
entry_cipher.pack(pady=5)

Button(scroll_frame, text="Dekripsi", command=decrypt).pack(pady=10)

Label(scroll_frame, text="Hasil Dekripsi (Teks):").pack()
output_text = Text(scroll_frame, height=6, width=100)
output_text.pack(pady=5)

Label(scroll_frame, text="Perbandingan Gambar:").pack(pady=(15, 5))
frame = Frame(scroll_frame)
frame.pack()

Label(frame, text="Sebelum Enkripsi").grid(row=0, column=0, padx=20)
Label(frame, text="Setelah Dekripsi").grid(row=0, column=1, padx=20)

canvas_before = Canvas(frame, width=400, height=300, bg='gray')
canvas_before.grid(row=1, column=0, padx=20)

canvas_after = Canvas(frame, width=400, height=300, bg='gray')
canvas_after.grid(row=1, column=1, padx=20)

Button(scroll_frame, text="Pilih Gambar Asli (Before)", command=load_original_image).pack(pady=10)
Button(scroll_frame, text="Reset", command=reset_all).pack()
info_before.pack(pady=(5, 0))
size_before.pack()
info_after.pack(pady=(10, 0))
size_after.pack(pady=(0, 20))

# === Scroll Mouse Support
def _on_mouse_wheel(event):
    main_canvas.yview_scroll(-1 * int(event.delta / 120), "units")

main_canvas.bind_all("<MouseWheel>", _on_mouse_wheel)
main_canvas.bind_all("<Button-4>", lambda e: main_canvas.yview_scroll(-1, "units"))  # Linux scroll up
main_canvas.bind_all("<Button-5>", lambda e: main_canvas.yview_scroll(1, "units"))   # Linux scroll down

root.mainloop()
