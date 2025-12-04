import mysql.connector
import datetime
import os
import sys
import qrcode
from barcode import Code128
from barcode.writer import ImageWriter
import configparser
import subprocess
import shutil

# Conditional import for Windows printing support
if sys.platform.startswith('win'):
    try:
        import win32print
    except ImportError:
        pass  # Handle import warning silently here, let GUI handle it if needed

# --- GLOBAL CONSTANTS ---
CONFIG_FILE = 'config.ini'
CODES_DIR = 'codes_generated'

# Ensure the storage directory exists
os.makedirs(CODES_DIR, exist_ok=True)


# --- 1. CONFIGURATION AND DATABASE FUNCTIONS ---

def create_default_config():
    """Creates a default config file if one doesn't exist."""
    config = configparser.ConfigParser()
    config['mysql'] = {
        'host': 'localhost',
        'user': 'root',
        'password': '',
        'database': 'code_manager_db'
    }
    with open(CONFIG_FILE, 'w') as configfile:
        config.write(configfile)


def load_config():
    """Loads DB settings from the config file, creating a default if needed."""
    if not os.path.exists(CONFIG_FILE):
        create_default_config()

    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)

    settings = {
        'host': config.get('mysql', 'host'),
        'user': config.get('mysql', 'user'),
        'password': config.get('mysql', 'password'),
        'database': config.get('mysql', 'database')
    }
    return settings


def save_config(settings):
    """Saves updated DB settings to the config file."""
    config = configparser.ConfigParser()
    config['mysql'] = settings
    with open(CONFIG_FILE, 'w') as configfile:
        config.write(configfile)


# Load the initial configuration, accessible globally within this module
DB_CONFIG = load_config()


def get_db_connection(use_db_name=True):
    """Establishes and returns a database connection using current config."""
    global DB_CONFIG

    # Reload config in case it was updated by the GUI
    DB_CONFIG = load_config()
    connect_params = DB_CONFIG.copy()

    if not use_db_name:
        connect_params.pop('database', None)

    if not connect_params.get('password'):
        connect_params.pop('password', None)

    try:
        conn = mysql.connector.connect(**connect_params)

        if use_db_name and conn.database is None:
            conn.database = DB_CONFIG['database']

        return conn

    except mysql.connector.Error:
        return None


def setup_database_tables(db_config):
    """Creates the database and necessary tables if they don't exist."""
    conn = get_db_connection(use_db_name=False)
    if not conn:
        return False, "Cannot connect to MySQL server. Check configuration."

    try:
        cursor = conn.cursor()

        db_name = db_config['database']
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")

        conn.database = db_name

        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS created_codes
                       (
                           id
                           INT
                           AUTO_INCREMENT
                           PRIMARY
                           KEY,
                           type
                           VARCHAR
                       (
                           10
                       ) NOT NULL,
                           data TEXT NOT NULL,
                           image_path VARCHAR
                       (
                           255
                       ) NOT NULL,
                           date_created DATETIME NOT NULL
                           )
                       """)

        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS scanned_codes
                       (
                           id
                           INT
                           AUTO_INCREMENT
                           PRIMARY
                           KEY,
                           data
                           TEXT
                           NOT
                           NULL,
                           date_scanned
                           DATETIME
                           NOT
                           NULL
                       )
                       """)

        conn.commit()
        cursor.close()
        conn.close()
        return True, f"Database '{db_name}' and tables are ready!"

    except mysql.connector.Error as err:
        return False, f"Error setting up database: {err}"


def backup_database(db_config):
    """Performs a database backup using mysqldump."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"code_manager_backup_{timestamp}.sql"

    try:
        command = [
            "mysqldump",
            "-u", db_config['user'],
        ]
        if db_config['password']:
            command.append(f"--password={db_config['password']}")

        command.extend([
            db_config['database'],
            "-r", backup_file
        ])

        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True, f"Database backed up successfully to: {backup_file}"

    except FileNotFoundError:
        return False, "mysqldump command not found. Ensure XAMPP's MySQL bin folder is in your system PATH."
    except subprocess.CalledProcessError as e:
        return False, f"Error during backup: {e.stderr.decode()}"
    except Exception as e:
        return False, f"An unexpected error occurred: {e}"


# --- 2. CODE GENERATION AND DATABASE STORAGE ---

def format_wifi_payload(ssid, password, auth_type):
    """Formats the data into the Wi-Fi Configuration string."""
    auth_map = {'WPA/WPA2': 'WPA', 'WEP': 'WEP', 'None': 'nopass'}
    ssid_esc = ssid.replace('\\', '\\\\').replace(';', '\\;')
    pass_esc = password.replace('\\', '\\\\').replace(';', '\\;')
    payload = f"WIFI:T:{auth_map.get(auth_type, 'WPA')};S:{ssid_esc};P:{pass_esc};;"
    return payload


def insert_code_metadata(type, data, image_path):
    """Inserts metadata about the created code into the database."""
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        sql = """
              INSERT INTO created_codes (type, data, image_path, date_created)
              VALUES (%s, %s, %s, %s) \
              """
        now = datetime.datetime.now()
        metadata_data = data[:250]
        values = (type, metadata_data, image_path, now)
        try:
            cursor.execute(sql, values)
            conn.commit()
            return True
        except mysql.connector.Error:
            return False
        finally:
            cursor.close()
            conn.close()
    return False


def generate_qr(data, filename):
    """Generates a single QR code image, saves it, and records metadata."""
    try:
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        full_path = os.path.join(CODES_DIR, f"{filename}_QR.png")
        img.save(full_path)

        insert_code_metadata('QR', data, full_path)
        return full_path
    except Exception:
        return None


def generate_barcode(data, filename):
    """Generates a single Code128 barcode image, saves it, and records metadata."""
    try:
        code128 = Code128(data, writer=ImageWriter())
        full_path_base = os.path.join(CODES_DIR, f"{filename}_BAR")

        code128.save(full_path_base)
        full_path = full_path_base + '.png'

        insert_code_metadata('BAR', data, full_path)
        return full_path
    except Exception:
        return None


# --- NEW FEATURE: BATCH GENERATION ---

def generate_batch_codes(code_type, prefix, start_num, end_num, pad_length, data_suffix=""):
    """
    Generates a batch of QR or Barcodes based on a numerical sequence.
    Returns (generated_count, list_of_errors).
    """
    generated_count = 0
    errors = []

    if code_type == 'QR':
        generator = generate_qr
        code_suffix = "QR"
    elif code_type == 'BAR':
        generator = generate_barcode
        code_suffix = "BAR"
    else:
        return 0, ["Invalid code type specified."]

    for i in range(start_num, end_num + 1):
        try:
            # 1. Format the data string and filename number
            num_str = str(i).zfill(pad_length)
            data = f"{prefix}{num_str}{data_suffix}"

            # 2. Format the unique filename
            # The generator functions append the final _QR.png or _BAR.png
            filename = f"{prefix}{num_str}"

            # 3. Generate and save
            path = generator(data, filename)

            if path:
                generated_count += 1
            else:
                errors.append(f"Failed to generate code for data: {data}")

        except Exception as e:
            errors.append(f"Exception for data {data}: {e}")

    return generated_count, errors


# --- 3. CRUD UPDATE AND REGENERATE ---

def update_code_and_regenerate(record_id, code_type, new_data, old_path):
    """
    Updates the database record with new data and regenerates the code image,
    replacing the old file.
    """
    conn = get_db_connection()
    if not conn:
        return False, "Cannot connect to database."

    cursor = conn.cursor()

    try:
        conn.start_transaction()
        full_path = old_path

        # 1. Regenerate image
        if os.path.exists(old_path):
            os.remove(old_path)

        # Determine unique filename base from old_path
        filename_base = os.path.splitext(os.path.basename(full_path))[0]
        # Remove the code type suffix (_QR or _BAR) for re-generation
        if filename_base.endswith('_QR'):
            filename = filename_base[:-3]
        elif filename_base.endswith('_BAR'):
            filename = filename_base[:-4]
        else:
            filename = filename_base  # Fallback

        # Ensure we use the correct generation function without DB insertion
        if code_type == 'QR':
            qr = qrcode.QRCode(version=1, box_size=10, border=4)
            qr.add_data(new_data)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            full_path = os.path.join(CODES_DIR, f"{filename}_QR.png")
            img.save(full_path)

        elif code_type == 'BAR':
            code128 = Code128(new_data, writer=ImageWriter())
            full_path_base = os.path.join(CODES_DIR, filename)
            code128.save(full_path_base)
            full_path = full_path_base + '.png'

            # 2. Update the DB record
        metadata_data = new_data[:250]
        sql = "UPDATE created_codes SET data = %s, image_path = %s WHERE id = %s"
        cursor.execute(sql, (metadata_data, full_path, record_id))

        conn.commit()

        return True, "Code regenerated and database updated."

    except Exception as e:
        conn.rollback()
        return False, f"Regeneration failed: {e}"
    finally:
        cursor.close()
        conn.close()


# --- 4. PRINTER DETECTION AND PRINTING FUNCTIONS ---

def get_installed_printers():
    """Returns a list of installed printer names based on OS."""
    if sys.platform.startswith('win'):
        try:
            if 'win32print' in sys.modules or os.name == 'nt':
                import win32print
                printers = [p[2] for p in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL)]
                return printers if printers else ["Windows Default Print Dialog"]
            else:
                return ["Windows Default Print Dialog (pywin32 not installed)"]
        except Exception:
            return ["Windows Default Print Dialog"]
    elif sys.platform == 'darwin' or sys.platform.startswith('linux'):
        try:
            result = subprocess.run(['lpstat', '-p', '-d'], capture_output=True, text=True, check=False)
            printers = [line.split()[1] for line in result.stdout.splitlines() if line.startswith('printer')]
            return printers if printers else ["Default CUPS Printer (lpr)"]
        except FileNotFoundError:
            return ["Default CUPS Printer (lpr)"]
    else:
        return ["Printing Not Fully Supported"]


def print_file_os(file_path, printer_name=None):
    """
    Attempts to send a file to the printer using OS-specific commands.
    Returns (True/False, message).
    """
    if not os.path.exists(file_path):
        return False, "File not found."

    if sys.platform.startswith('win'):
        try:
            os.startfile(file_path, "print")
            return True, "Printing initiated via Windows OS dialog."
        except Exception as e:
            return False, f"Windows printing failed. Error: {e}"
    elif sys.platform == 'darwin' or sys.platform.startswith('linux'):
        command = ['lpr']
        if printer_name and "Default CUPS Printer" not in printer_name:
            command.extend(['-P', printer_name])

        command.append(file_path)

        try:
            subprocess.run(command, check=True, capture_output=True)
            return True, f"File sent to print spooler (Printer: {printer_name or 'Default'})."
        except subprocess.CalledProcessError as e:
            return False, f"Printing failed (lpr error): {e.stderr.decode()}"
        except FileNotFoundError:
            return False, "The 'lpr' command was not found. Is CUPS installed?"
    else:
        return False, "Printing not supported on this operating system."