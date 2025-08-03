import os

# import dotenv
# from dotenv import load_dotenv
# load_dotenv()

import pymysql # Menggunakan pymysql
from datetime import datetime, timedelta
import secrets # Untuk menghasilkan token yang aman

# --- Konfigurasi Database (diambil dari variabel lingkungan) ---
DB_HOST = os.environ.get('DB_HOST')
DB_PORT = int(os.environ.get('DB_PORT', 3306))
DB_USER = os.environ.get('DB_USER')
DB_PASS = os.environ.get('DB_PASS')
DB_NAME = os.environ.get('DB_NAME')

# Validasi dasar: Pastikan kredensial database ada
# if not all([DB_HOST, DB_USER, DB_PASS, DB_NAME]):
#     raise ValueError("Variabel lingkungan database (DB_HOST, DB_USER, DB_PASS, DB_NAME) harus diatur.")


def get_db_connection():
    """
    Membuat dan mengembalikan objek koneksi ke database.
    Akan melempar pengecualian jika koneksi gagal.
    """
    try:
        conn = pymysql.connect( # Menggunakan pymysql.connect
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASS,
            database=DB_NAME,
            cursorclass=pymysql.cursors.DictCursor # Mengaktifkan DictCursor secara default
        )
        return conn
    except pymysql.Error as err: # Menangkap error pymysql
        print(f"Error: Tidak dapat terhubung ke database: {err}")
        raise # Melemparkan kembali error agar aplikasi bisa menanganinya


def init_db():
    """
    Menginisialisasi database dengan membuat tabel 'subscribers' jika belum ada.
    Menambahkan kolom email_sent_dayX hingga day30 secara otomatis.
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        # Saat menggunakan DictCursor secara default di get_db_connection,
        # kita perlu memastikan cursor untuk operasi DDL/DML adalah non-dict.
        # Atau, bisa juga menggunakan DictCursor di sini dan mengubah fetchone/fetchall.
        # Untuk init_db, cursor default sudah cukup.
        cursor = conn.cursor()

        # SQL untuk membuat tabel 'subscribers'
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS subscribers2 (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            email VARCHAR(255) NOT NULL UNIQUE,
            subscribed_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_confirmed BOOLEAN DEFAULT FALSE,
            confirmation_token VARCHAR(255) UNIQUE,
            token_expiry DATETIME,
            last_email_sent_day INT DEFAULT 0
        );
        """
        cursor.execute(create_table_sql)
        print("Tabel 'subscribers' berhasil dibuat atau sudah ada.")

        # Menambahkan kolom email_sent_dayX untuk setiap hari email yang terjadwal
        # Loop dari hari 1 hingga hari 30
        for i in range(1, 31):
            column_name = f'email_sent_day{i}'
            try:
                add_column_sql = f"ALTER TABLE subscribers2 ADD COLUMN {column_name} BOOLEAN DEFAULT FALSE;"
                cursor.execute(add_column_sql)
                # print(f"Kolom '{column_name}' berhasil ditambahkan atau sudah ada.")
            except pymysql.err.ProgrammingError as err: # Menangkap error pymysql untuk duplicate column
                # Error code 1060 berarti kolom sudah ada (Duplicate column name)
                if err.args[0] == 1060:
                    pass # Abaikan jika kolom sudah ada
                else:
                    print(f"Error saat menambahkan kolom '{column_name}': {err}")
                    raise

        conn.commit()
    except pymysql.Error as err:
        print(f"Error saat inisialisasi database: {err}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def add_pending_subscriber(email, name):
    """
    Menambahkan subscriber baru dengan status 'pending' dan menghasilkan token konfirmasi.
    Token akan memiliki masa berlaku 24 jam.
    Mengembalikan tuple (True, token) jika berhasil, atau (False, None) jika gagal atau email sudah ada.
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor() # Gunakan cursor default untuk operasi ini

        # Periksa apakah email sudah ada
        cursor.execute("SELECT id FROM subscribers2 WHERE email = %s", (email,))
        if cursor.fetchone():
            print(f"Email '{email}' sudah terdaftar.")
            return False, None

        # Hasilkan token konfirmasi yang aman dan atur masa berlakunya
        confirmation_token = secrets.token_urlsafe(32) # String acak 32 byte, aman untuk URL
        token_expiry = datetime.now() + timedelta(hours=24) # Berlaku 24 jam

        insert_sql = """
        INSERT INTO subscribers2 (name, email, is_confirmed, confirmation_token, token_expiry)
        VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(insert_sql, (name, email, True, confirmation_token, token_expiry))
        conn.commit()
        # print(f"Subscriber pending '{email}' berhasil ditambahkan dengan token '{confirmation_token}'.")
        return True, confirmation_token
    except pymysql.Error as err: # Menangkap error pymysql
        print(f"Error saat menambahkan subscriber pending: {err}")
        return False, None
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def confirm_subscriber(token):
    """
    Mengkonfirmasi subscriber menggunakan token.
    Memeriksa validitas token dan masa berlakunya.
    Mengembalikan dictionary data subscriber (email dan nama) jika berhasil, None jika token tidak valid/kadaluarsa.
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor() # get_db_connection sudah mengembalikan DictCursor secara default

        # Cari subscriber berdasarkan token dan pastikan belum dikonfirmasi dan token belum kadaluarsa
        select_sql = """
        SELECT id, name, email, is_confirmed, token_expiry FROM subscribers2
        WHERE confirmation_token = %s
        """
        cursor.execute(select_sql, (token,))
        subscriber = cursor.fetchone()

        if not subscriber:
            print(f"Token konfirmasi tidak ditemukan: {token}")
            return None

        if subscriber['is_confirmed']:
            print(f"Subscriber dengan token '{token}' sudah dikonfirmasi.")
            return None # Sudah dikonfirmasi, anggap saja tidak valid lagi untuk konfirmasi ulang

        # Gunakan timezone-aware datetime.now() jika Anda menggunakan timezone di database.
        # Untuk kasus sederhana ini, kita asumsikan keduanya adalah naive datetime.
        if subscriber['token_expiry'] and datetime.now() > subscriber['token_expiry']:
            print(f"Token konfirmasi kadaluarsa untuk: {subscriber['email']}")
            return None # Token sudah kadaluarsa

        # Update status subscriber menjadi dikonfirmasi dan hapus token/expiry
        # Juga set subscribed_date ke waktu konfirmasi jika ingin melacak dari sana
        update_sql = """
        UPDATE subscribers2
        SET is_confirmed = TRUE, confirmation_token = NULL, token_expiry = NULL, subscribed_date = %s
        WHERE id = %s
        """
        cursor.execute(update_sql, (datetime.now(), subscriber['id']))
        conn.commit()
        print(f"Subscriber '{subscriber['email']}' berhasil dikonfirmasi.")
        # Mengembalikan data subscriber yang dikonfirmasi
        return {'email': subscriber['email'], 'name': subscriber['name']}

    except pymysql.Error as err: # Menangkap error pymysql
        print(f"Error saat mengkonfirmasi subscriber: {err}")
        return None
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def get_all_confirmed_subscribers():
    """
    Mengambil semua data subscriber yang sudah dikonfirmasi.
    Digunakan oleh scheduler untuk mengirim email.
    Mengembalikan list dari dictionary subscriber.
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor() # get_db_connection sudah mengembalikan DictCursor secara default

        # Ambil semua kolom, termasuk status email_sent_dayX
        columns = ["id", "name", "email", "subscribed_date", "last_email_sent_day"]
        # Menambahkan semua kolom email_sent_dayX hingga day30
        for i in range(1, 31):
            columns.append(f"email_sent_day{i}")

        select_sql = f"SELECT {', '.join(columns)} FROM subscribers2 WHERE is_confirmed = TRUE"
        cursor.execute(select_sql)
        subscribers = cursor.fetchall()
        return subscribers
    except pymysql.Error as err: # Menangkap error pymysql
        print(f"Error saat mengambil semua subscriber yang dikonfirmasi: {err}")
        return []
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def update_subscriber_email_status(email, day_number):
    """
    Memperbarui status pengiriman email untuk subscriber tertentu pada hari tertentu.
    Juga memperbarui 'last_email_sent_day' jika 'day_number' lebih besar dari yang sudah ada.
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor() # Gunakan cursor default untuk operasi ini

        column_name = f'email_sent_day{day_number}'
        update_sql = f"""
        UPDATE subscribers2
        SET {column_name} = TRUE,
            last_email_sent_day = GREATEST(last_email_sent_day, %s)
        WHERE email = %s
        """
        cursor.execute(update_sql, (day_number, email))
        conn.commit()
        # print(f"Status email Hari {day_number} untuk '{email}' berhasil diperbarui.")
    except pymysql.Error as err: # Menangkap error pymysql
        print(f"Error saat memperbarui status email Hari {day_number} untuk '{email}': {err}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def get_subscriber_by_email(email):
    """
    Mengambil data subscriber berdasarkan email.
    Mengembalikan dictionary data subscriber jika ditemukan, None jika tidak.
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor() # get_db_connection sudah mengembalikan DictCursor secara default
        select_sql = "SELECT id, name, email, is_confirmed FROM subscribers2 WHERE email = %s"
        cursor.execute(select_sql, (email,))
        subscriber = cursor.fetchone()
        return subscriber
    except pymysql.Error as err: # Menangkap error pymysql
        print(f"Error saat mengambil subscriber by email '{email}': {err}")
        return None
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def get_subscribers_count():
    """
    Mengambil jumlah total subscriber yang sudah dikonfirmasi.
    Meskipun tidak digunakan di halaman utama lagi, fungsi ini tetap berguna
    untuk keperluan administrasi atau dashboard internal.
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor() # Gunakan cursor default untuk operasi ini
        cursor.execute("SELECT COUNT(id) FROM subscribers2 WHERE is_confirmed = TRUE")
        count = cursor.fetchone()[0]
        return count
    except pymysql.Error as err: # Menangkap error pymysql
        print(f"Error saat mengambil jumlah subscriber: {err}")
        return 0
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# Contoh penggunaan (bisa dihapus jika tidak diperlukan untuk pengujian langsung)
if __name__ == '__main__':
    # Pastikan Anda telah mengatur variabel lingkungan database sebelum menjalankan ini
    print("Menjalankan inisialisasi database...")
    init_db()

    # Contoh penambahan subscriber pending
    # print("\nMenambahkan subscriber pending...")
    # added, token = add_pending_subscriber("test@example.com", "Test User")
    # if added:
    #     print(f"Added pending subscriber. Token: {token}")
    # else:
    #     print("Failed to add pending subscriber or email already exists.")

    # Contoh konfirmasi subscriber (gunakan token yang dihasilkan di atas)
    # print("\nMengkonfirmasi subscriber...")
    # if added and token:
    #     confirmed_data = confirm_subscriber(token)
    #     if confirmed_data:
    #         print(f"Subscriber confirmed: {confirmed_data['email']}")
    #     else:
    #         print("Failed to confirm subscriber.")

    # Contoh mengambil semua subscriber yang dikonfirmasi
    # print("\nMengambil semua subscriber yang dikonfirmasi:")
    # confirmed_subs = get_all_confirmed_subscribers()
    # for sub in confirmed_subs:
    #     print(sub)

    # Contoh memperbarui status email
    # if confirmed_subs:
    #     first_sub_email = confirmed_subs[0]['email']
    #     print(f"\nMemperbarui status email Hari 1 untuk {first_sub_email}...")
    #     update_subscriber_email_status(first_sub_email, 1)

    # print("\nMengambil jumlah subscriber yang dikonfirmasi:")
    # count = get_subscribers_count()
    # print(f"Jumlah subscriber dikonfirmasi: {count}")