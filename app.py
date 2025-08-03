import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from email.header import Header
from datetime import datetime, date, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, request, render_template, redirect, url_for, flash

# Import semua fungsi utilitas database dari file database_utils.py kita
import database_utils

# --- Konfigurasi Aplikasi dan Email (diambil dari variabel lingkungan) ---
# SITE_URL: URL dasar aplikasi Anda (penting untuk tautan konfirmasi).
# Contoh: 'http://localhost:5000' untuk pengembangan lokal, atau 'https://domainanda.com' untuk produksi.
# import dotenv
# from dotenv import load_dotenv
# load_dotenv()
SITE_URL = os.environ.get('SITE_URL')

# Kredensial akun email SMTP Anda
MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
MAIL_PASSWORD2 = os.environ.get('MAIL_PASSWORD2')
MAIL_DEFAULT_SENDER=os.environ.get('MAIL_DEFAULT_SENDER')
CUSTOM_SENDER_NAME=os.environ.get('CUSTOM_SENDER_NAME')
# Server SMTP dan Port (contoh: smtp.gmail.com dan 587 untuk Gmail)
MAIL_SERVER = os.environ.get('MAIL_SERVER')
MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
# Kunci rahasia Flask untuk mengamankan sesi dan pesan flash. Harus diatur nilai unik yang kuat di produksi.
SECRET_KEY = os.environ.get('SECRET_KEY')

# Detail koneksi database MariaDB (digunakan oleh database_utils.py)
# Variabel-variabel ini hanya didefinisikan di sini untuk tujuan validasi awal.
# Nilai sebenarnya akan diakses oleh database_utils dari os.environ.
DB_HOST = os.environ.get('DB_HOST')
DB_PORT = int(os.environ.get('DB_PORT', 3306))
DB_USER = os.environ.get('DB_USER')
DB_PASS = os.environ.get('DB_PASS') # Kata sandi database
DB_NAME = os.environ.get('DB_NAME')

# Validasi: Pastikan semua variabel lingkungan penting sudah diatur.
# Jika ada yang kosong, aplikasi akan berhenti dengan error.
# if not all([SITE_URL, MAIL_USERNAME, MAIL_PASSWORD, MAIL_SERVER, SECRET_KEY, DB_HOST, DB_USER, DB_PASS, DB_NAME]):
#     raise ValueError("Semua variabel lingkungan yang dibutuhkan (SITE_URL, MAIL_USERNAME, MAIL_PASSWORD, MAIL_SERVER, SECRET_KEY, DB_HOST, DB_USER, DB_PASS, DB_NAME) harus diatur.")


# --- Konfigurasi Autoresponder ---
# Dictionary yang memetakan nomor hari (sejak berlangganan) ke file template email.
# 'confirm_email' adalah template khusus untuk email konfirmasi.
# Pastikan Anda memiliki file-file ini di folder 'emails' Anda!
EMAIL_TEMPLATES = {
    'confirm_email': 'emails/confirm_email.html', # Template email konfirmasi
    1: 'emails/day1.html',
    2: 'emails/day2.html',
    3: 'emails/day3.html',
    4: 'emails/day4.html',
    5: 'emails/day5.html',
    6: 'emails/day6.html',
    7: 'emails/day7.html',
    11: 'emails/day11.html',
    12: 'emails/day12.html',
    15: 'emails/day15.html',
    16: 'emails/day16.html',
    17: 'emails/day17.html',
    18: 'emails/day18.html',
    20: 'emails/day20.html',
    21: 'emails/day21.html',
    23: 'emails/day23.html',
    25: 'emails/day25.html',
    27: 'emails/day27.html',
    29: 'emails/day29.html',
    30: 'emails/day30.html', # Email terakhir terjadwal pada hari ke-30
}

# Inisialisasi aplikasi Flask
app = Flask(__name__)
app.secret_key = SECRET_KEY # Mengatur kunci rahasia untuk Flask
# Inisialisasi scheduler latar belakang dari APScheduler
scheduler = BackgroundScheduler()

# --- Fungsi Utilitas Email ---
def send_email(to_email, subject, plain_body, html_body, sender_email=formataddr((str(Header(CUSTOM_SENDER_NAME, 'utf-8')), MAIL_DEFAULT_SENDER))):
    """
    Mengirim email multipart (versi teks biasa dan HTML).
    Email multipart memastikan kompatibilitas luas di berbagai klien email.
    """
    msg = MIMEMultipart('alternative')
    msg['From'] = sender_email
    msg['To'] = to_email
    msg['Subject'] = subject

    # msg2 = MIMEText(f"Horee optin baru! -> Nama : {request.form.get('name')}, Email : {to_email}")
    # msg2["Subject"] = "Selamat dapet optin baru"
    # msg2["From"] = "laptoplifestyleacademy2@gmail.com"
    # msg2["To"] = "amunibf@gmail.com"
    # sender = "laptoplifestyleacademy2@gmail.com"

    # Melampirkan bagian teks biasa (fallback jika klien tidak mendukung HTML)
    part1 = MIMEText(plain_body, 'plain', 'utf-8')
    msg.attach(part1)

    # Melampirkan bagian HTML
    # part2 = MIMEText(html_body, 'html', 'utf-8')
    # msg.attach(part2)

    try:
        # Membuat koneksi SMTP, memulai TLS (Transport Layer Security) untuk enkripsi
        # dan login ke server SMTP.
        # with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server2:
        #     server2.login(sender, MAIL_PASSWORD2)
        #     server2.send_message(msg2)

        with smtplib.SMTP(MAIL_SERVER, MAIL_PORT) as server:
            server.starttls() # Mengenkripsi koneksi
            server.login(MAIL_USERNAME, MAIL_PASSWORD)
            server.send_message(msg) # Mengirim pesan email
            print(f"Email multipart '{subject}' berhasil dikirim ke: {to_email}")
            return True

    except Exception as e:
        print(f"Gagal mengirim email multipart ke {to_email} ({subject}): {e}")
        return False



def load_email_template(filepath, name, **kwargs):
    """
    Memuat subjek, isi teks biasa, dan isi HTML dari file template email.
    Menerima argumen kata kunci (kwargs) tambahan untuk mengganti placeholder di template
    (misal: confirmation_link).
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

            # Memisahakan kontena baris demi baris untuk mengekstrak subjeknya
            lines = content.split('\n')
            subject_line = lines[0].replace('Subject: ', '').strip().replace('{name}', name)
            remaining_content = '\n'.join(lines[1:]).strip()
            # print('subject_line :',subject_line)


            # Memisayhjkan akonten yang tersisa menjadi bagian teks biasa dan HTML
            # Delimiter '---HTML_PART---' digunakan untuk memisahkan kedua bagian.
            parts = remaining_content.split('---HTML_PART---', 1) # Hanya pisahkan sekali
            plain_content = parts[0].strip()
            html_content = parts[1].strip() if len(parts) > 1 else ""

            # Mengganti placeholder {name}
            plain_content = plain_content.replace('{name}', name)
            html_content = html_content.replace('{name}', name)
            # print('plain_content :',plain_content)
            # print('html_content : ',html_content)

            # Mengganti placeholder tambahan dari kwargs (misal: {confirmation_link})
            for key, value in kwargs.items():
                plain_content = plain_content.replace('{' + key + '}', str(value))
                html_content = html_content.replace('{' + key + '}', str(value))

            return subject_line, plain_content, html_content
    except FileNotFoundError:
        print(f"ERROR: Template email tidak ditemukan di {filepath}")
        return None, None, None
    except IndexError:
        print(f"ERROR: Format template email salah di {filepath}. Pastikan ada 'Subject:' di baris pertama dan '---HTML_PART---' untuk memisahkan bagian.")
        return None, None, None

# --- Logika Pendaftaran dan Konfirmasi Subscriber ---
def register_pending_subscriber_and_send_confirm_email(email, name):
    """
    Mendaftarkan subscriber baru sebagai 'pending' (belum dikonfirmasi)
    dan mengirimkan email konfirmasi dengan tautan unik.
    Mengembalikan True dan token jika berhasil, False jika email sudah ada atau gagal.
    """

    msg2 = MIMEText(f"Horee optin baru! -> Nama : {name}, Email : {email}")
    msg2["Subject"] = "MMO!"
    msg2["From"] = "laptoplifestyleacademy2@gmail.com"
    msg2["To"] = "amunibf@gmail.com"
    sender = "laptoplifestyleacademy2@gmail.com"

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server2:
        server2.login(sender, 'pjry zhak qmki dpuy')
        server2.send_message(msg2)

    is_added, token = database_utils.add_pending_subscriber(email, name)
    if is_added and token:
        # Membuat tautan konfirmasi lengkap menggunakan SITE_URL
        confirmation_link = f"{SITE_URL}{url_for('confirm_subscription', token=token, _external=False)}"

        # Memuat template email konfirmasi
        subject, plain_body, html_body = load_email_template(
            EMAIL_TEMPLATES['confirm_email'],
            name,
            confirmation_link=confirmation_link # Meneruskan tautan sebagai placeholder
        )
        # print("bababa",plain_body,html_body)
        if subject and plain_body and html_body:
            # Mengirim email konfirmasi
            
            if send_email(email, subject, plain_body, html_body):
                print(f"Email konfirmasi terkirim ke {email} dengan token {token}.")
                return True
            else:
                print(f"Gagal mengirim email konfirmasi ke {email}.")
                return False
        else:
            print(f"ERROR: Gagal memuat template email konfirmasi. Email tidak terkirim.")
            return False
        
    elif not is_added: # Email sudah ada
        return False
    return False

# --- Logika Pendaftaran dan Konfirmasi Subscriber ---
def register_pending_subscriber_and_send_confirm_email2(email, name):
    msg2 = MIMEText(f"MMO! -> Nama : {name}, Email : {email}")
    msg2["Subject"] = "Selamat dapet optin baru"
    msg2["From"] = "laptoplifestyleacademy2@gmail.com"
    msg2["To"] = "amunibf@gmail.com"
    sender = "laptoplifestyleacademy2@gmail.com"

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server2:
        server2.login(sender, MAIL_PASSWORD2)
        server2.send_message(msg2)

    is_added, token = database_utils.add_pending_subscriber(email, name)
    if is_added and token:
        # Membuat tautan konfirmasi lengkap menggunakan SITE_URL
        confirmation_link = f"{SITE_URL}{url_for('confirm_subscription', token=token, _external=False)}"

        # Memuat template email konfirmasi
        subject, plain_body, html_body = load_email_template(
            EMAIL_TEMPLATES['confirm_email'],
            name,
            confirmation_link=confirmation_link # Meneruskan tautan sebagai placeholder
        )
        # print("bababa",plain_body,html_body)
        if subject and plain_body and html_body:
            # Mengirim email konfirmasi
            
            if send_email(email, subject, plain_body, html_body):
                print(f"Email konfirmasi terkirim ke {email} dengan token {token}.")
                return True
            else:
                print(f"Gagal mengirim email konfirmasi ke {email}.")
                return False
        else:
            print(f"ERROR: Gagal memuat template email konfirmasi. Email tidak terkirim.")
            return False
        
    elif not is_added: # Email sudah ada
        return False
    return False

def send_day1_email_to_confirmed_subscriber(subscriber_data):
    """
    Mengirim email Hari 1 kepada subscriber yang baru saja dikonfirmasi.
    Fungsi ini dipicu segera setelah konfirmasi berhasil.
    """
    email = subscriber_data['email']
    name = subscriber_data['name']

    # Memeriksa apakah template Hari 1 sudah dikonfigurasi
    if 1 in EMAIL_TEMPLATES:
        subject, plain_body, html_body = load_email_template(EMAIL_TEMPLATES[1], name)
        if subject and plain_body and html_body:
            if send_email(email, subject, plain_body, html_body):
                database_utils.update_subscriber_email_status(email, 1) # Menandai Hari 1 sebagai sudah dikirim
                print(f"Email Hari 1 terkirim ke {email} setelah konfirmasi.")
                return True
        else:
            print(f"ERROR: Gagal memuat template Hari 1. Email Hari 1 tidak terkirim ke {email}")
    else:
        print(f"Peringatan: Hari 1 tidak terdaftar dalam EMAIL_TEMPLATES. Email pertama tidak terkirim.")
    return False

def run_daily_autoresponder_check():
    """
    Fungsi ini dijalankan setiap hari oleh scheduler APScheduler.
    Fungsi ini memeriksa semua subscriber yang SUDAH DIKONFIRMASI dan mengirimkan email
    sesuai dengan jadwal autoresponder.
    """
    print(f"[{datetime.now()}] Menjalankan pemeriksaan harian autoresponder...")
    # Mengambil semua subscriber yang sudah dikonfirmasi dari database
    subscribers = database_utils.get_all_confirmed_subscribers()
    if not subscribers:
        print("Tidak ada subscriber yang dikonfirmasi di database.")
        return

    # Mengurutkan hari-hari terjadwal untuk memastikan email dikirim dalam urutan yang benar
    # Filter hanya hari-hari yang merupakan integer (angka), bukan 'confirm_email'
    sorted_schedule_days = sorted([d for d in EMAIL_TEMPLATES.keys() if isinstance(d, int)])

    for sub_row in subscribers:
        subscriber_email = sub_row['email']
        subscriber_name = sub_row['name']
        # Mengambil hanya bagian tanggal dari objek datetime 'subscribed_date'
        subscribed_date_obj = sub_row['subscribed_date'].date()
        last_email_sent_day = sub_row['last_email_sent_day']

        # Menghitung jumlah hari yang telah berlalu sejak berlangganan (0 untuk hari berlangganan itu sendiri)
        days_since_subscribed_actual = (date.today() - subscribed_date_obj).days
        # Mengubahnya menjadi hitungan hari berbasis 1 untuk perbandingan dengan hari terjadwal (Hari 1, Hari 3, dst.)
        current_schedule_day_check = days_since_subscribed_actual + 1
        print("-----------------")
        print("Data : ",subscriber_email,subscriber_name,"days_since_subscribed_actual : ",days_since_subscribed_actual,"current_schedule_day_check : ",current_schedule_day_check)
        print("-----------------")

        for scheduled_day in sorted_schedule_days:
            # Lewati email Hari 1 jika sudah dikirim selama proses konfirmasi
            if scheduled_day == 1 and sub_row.get(f'email_sent_day{scheduled_day}', False): # Menggunakan f-string untuk mendapatkan nama kolom yang benar
                continue

            # Mendapatkan status pengiriman email untuk hari terjadwal saat ini
            # Default ke 0 (False) jika kolom tidak ditemukan (meskipun seharusnya tidak terjadi setelah migrasi DB)
            email_sent_for_scheduled_day_flag = sub_row.get(f'email_sent_day{scheduled_day}', False)

            print("current_schedule_day_check",current_schedule_day_check)
            print("scheduled_day",scheduled_day)
            print("email_sent_for_scheduled_day_flag",email_sent_for_scheduled_day_flag)
            print("last_email_sent_day",last_email_sent_day)
            print("-----------------")

            # Logika untuk mengirim email terjadwal:
            # 1. Apakah hari ini adalah hari terjadwal ATAU apakah hari terjadwal sudah terlewat (untuk mengejar email yang terlewat)?
            # 2. Apakah email untuk hari terjadwal spesifik ini BELUM dikirim?
            # 3. Apakah hari terjadwal ini lebih besar dari hari email terakhir yang dikirim (untuk memastikan urutan yang benar)?
            if (current_schedule_day_check >= scheduled_day) and \
               (not email_sent_for_scheduled_day_flag) and \
               (last_email_sent_day < scheduled_day):

                print(f"  - Subscriber {subscriber_email}: Hari {current_schedule_day_check} sejak berlangganan. Sedang cek kirim email Hari {scheduled_day}.")

                # Memastikan template untuk hari terjadwal ini sudah dikonfigurasi
                if scheduled_day in EMAIL_TEMPLATES:
                    filepath = EMAIL_TEMPLATES[scheduled_day]
                    subject, plain_body, html_body = load_email_template(filepath, subscriber_name)

                    if subject and plain_body and html_body:
                        if send_email(subscriber_email, subject, plain_body, html_body):
                            # Memperbarui status database setelah berhasil mengirim
                            database_utils.update_subscriber_email_status(subscriber_email, scheduled_day)
                            print(f"    Email Hari {scheduled_day} terkirim ke {subscriber_email}")
                        else:
                            print(f"    Gagal mengirim email Hari {scheduled_day} ke {subscriber_email}. Akan coba lagi nanti.")
                    else:
                        print(f"    Gagal memuat template untuk Hari {scheduled_day}. Email tidak terkirim.")
                else:
                    print(f"    Peringatan: Template untuk Hari {scheduled_day} tidak ditemukan dalam EMAIL_TEMPLATES.")


# --- Flask Routes ---
@app.route('/')
def home():
    """Merender halaman utama aplikasi (halaman opt-in)."""
    # Tidak lagi mengambil atau merender jumlah subscriber.
    return render_template('index.html') # Tidak lagi meneruskan 'subscribers_count'

@app.route('/blog')
def home2():
    """Merender halaman utama aplikasi (halaman opt-in)."""
    # Tidak lagi mengambil atau merender jumlah subscriber.
    return render_template('index2.html') # Tidak lagi meneruskan 'subscribers_count'

@app.route('/add_subscriber', methods=['POST'])
def add_subscriber_route():
    """Menangani pendaftaran subscriber baru melalui formulir web."""
    email = request.form['email']
    name = request.form.get('name') # Nama bersifat opsional, default ke 'Pelanggan'
    if email:
        # Memeriksa apakah email sudah ada di database
        existing_subscriber = database_utils.get_subscriber_by_email(email)
        if existing_subscriber:
            if existing_subscriber['is_confirmed']:
                # flash(f'Email "{email}" sudah terdaftar dan dikonfirmasi.', 'warning')
                flash('You have already signed up with this email.','warning')
            else:
                flash(f'I already sent your ebook to "{email}". After signing up, my email might land in your Promotions or Spam folder. 👉 Please check those folders and drag the email into your Primary inbox so you don’t miss any awesome tips!.(And don’t forget to hit “Not Spam” or “Add me to Contacts” – John Smith 😉).', 'warning')
            return redirect(url_for('home'))

        # Jika email belum ada, daftarkan sebagai pending dan kirim email konfirmasi
        if register_pending_subscriber_and_send_confirm_email(email, name):
            flash(f'I already sent your ebook to your email. After signing up, my email might land in your "Promotions" or "Spam Folder". 👉 Please check those folders and drag the email into your Primary inbox so you don’t miss any awesome tips!.(And don’t forget to hit “Not Spam” or “Add me to Contacts” – John Smith 😉).', 'success')
        else:
            flash(f'Gagal memproses pendaftaran untuk "{email}". Mohon coba lagi nanti.', 'danger')
            return redirect(url_for('home'))
    # flash('Alamat email tidak valid.', 'danger')
    return redirect(url_for('home'))

@app.route('/confirm')
def confirm_subscription():
    """Menangani konfirmasi email melalui tautan unik (token) yang dikirim."""
    token = request.args.get('token')
    if not token:
        flash('Token konfirmasi tidak ditemukan.', 'danger')
        return redirect(url_for('home'))

    # Mengkonfirmasi subscriber di database menggunakan token
    subscriber_data = database_utils.confirm_subscriber(token)
    if subscriber_data:
        # Jika konfirmasi berhasil, segera kirim email Hari 1
        send_day1_email_to_confirmed_subscriber(subscriber_data)
        flash(f'Email Anda "{subscriber_data["email"]}" telah berhasil dikonfirmasi! Selamat datang!', 'success')
        # Mengarahkan ke halaman konfirmasi yang baru, meneruskan data subscriber
        return redirect(url_for('confirmed_page', email=subscriber_data['email'], name=subscriber_data['name']))
    else:
        flash('Tautan konfirmasi tidak valid atau sudah digunakan.', 'danger')
        return redirect(url_for('home'))

@app.route('/confirmed')
def confirmed_page():
    """Merender halaman sukses konfirmasi setelah email berhasil dikonfirmasi."""
    # Mengambil email dan nama dari parameter URL untuk ditampilkan di halaman
    email = request.args.get('email', 'N/A')
    name = request.args.get('name', 'Pelanggan')
    return render_template('confirmed.html', email=email, name=name)

@app.route('/trigger_daily_check')
def trigger_daily_check_manual_route():
    """
    Rute ini memungkinkan pemicuan manual pemeriksaan autoresponder harian.
    Berguna untuk debugging atau pengujian di lingkungan pengembangan.
    Di produksi, sebaiknya diamankan atau dihapus.
    """
    run_daily_autoresponder_check()
    flash('Pemeriksaan penjadwalan harian manual telah dipicu. Lihat konsol server Anda untuk log.', 'info')
    return redirect(url_for('home'))

# --- Penyiapan APScheduler ---
def start_scheduler2():
    """Memulai APScheduler di latar belakang."""
    # Menambahkan tugas (job) untuk menjalankan run_daily_autoresponder_check
    # pada jadwal 'cron' (seperti cronjob Linux) setiap hari jam 07:00 pagi WIB
    scheduler.add_job(run_daily_autoresponder_check, 'cron', hour=22, minute=1, id='daily_autoresponder4')

    scheduler.start() # Memulai scheduler
    print("\n--- Scheduler APScheduler Dimulai ---")
    print(" - Pemeriksaan autoresponder harian akan berjalan setiap hari pukul 08:40 WIB.")

start_scheduler2()

if __name__ == '__main__':
    # Inisialisasi tabel database saat aplikasi dimulai
    database_utils.init_db()
    # database_utils.init_db()
    # confirmed_subs = database_utils.get_all_confirmed_subscribers()
    # for sub in confirmed_subs:
    #     print(sub)
    # run_daily_autoresponder_check()
    # Memulai scheduler untuk tugas otomatis
    start_scheduler2()
    # Menjalankan aplikasi Flask.
    # Untuk produksi, gunakan server WSGI seperti Gunicorn atau uWSGI.
    # 'debug=False' harus selalu diatur di produksi.
    # 'use_reloader=False' penting saat menggunakan scheduler untuk menghindari tugas ganda.
    app.run(host='0.0.0.0', port=5002, debug=False, use_reloader=False)
    # app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=True)