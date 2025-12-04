# 🏷️ Configurable Code Manager App (CRUD, Printing & Batch)

This is a comprehensive desktop application built with **Tkinter** for the GUI and **MySQL Connector** for backend data management. It allows users to **generate, manage, and print** both **QR Codes** and **Code 128 Barcodes**, providing full **CRUD (Create, Read, Update, Delete)** functionality and robust database control, including new **Batch Generation** features.

## ✨ Features Overview

| Category | Feature | Description |
| :--- | :--- | :--- |
| **Code Generation** | **Single QR Code** | Generates QR codes for general text, links, and specialized **Wi-Fi configuration** payloads. |
| **Code Generation** | **Batch Generation (New)** | Generates a sequential batch of numbered QR Codes or Code 128 Barcodes using customizable prefixes, suffixes, start/end numbers, and padding. |
| **Code Generation** | **Code 128 Barcodes** | Generates standard Code 128 barcodes, suitable for alphanumeric data (e.g., inventory tracking). |
| **Data Management** | **MySQL Backend** | Stores code metadata (type, data snippet, file path, creation date) in a configurable MySQL database. |
| **CRUD** | **Atomic Update & Regenerate** | Allows editing of a code's data; the system **regenerates the image**, deletes the old file, and updates the database record within a robust transaction for safety. |
| **System** | **Configuration** | Uses a `config.ini` file for easy management of MySQL connection settings. |
| **System** | **DB Utilities** | Includes functionality for **Database Setup/Table Creation**, **Database Backup** (using `mysqldump`), and a **DANGER ZONE** for complete database and file folder deletion. |
| **Output** | **Printing** | Supports cross-platform printing of generated code images to system printers (Windows `os.startfile`, Linux/macOS `lpr`) after detecting available printers. |

## ⚙️ Prerequisites

Before running the application, ensure you have the following installed:

1.  **Python 3.x**
2.  **MySQL Server** (accessible locally or via network).
3.  **Required Python Libraries:**
    ```bash
    pip install mysql-connector-python tk qrcode python-barcode Pillow
    # Optional: For better Windows printer control
    pip install pywin32 
    ```
4.  **PATH Configuration (Optional but Recommended):** For the "Backup Database" feature to work, the directory containing the `mysqldump` executable (usually in your MySQL/XAMPP `bin` folder) must be added to your system's environment PATH.

## 🚀 Getting Started

1.  **Clone the repository** (or save the provided Python files). Ensure all files (`code_manager_app.py`, `db_utils.py`, and `config.ini`) are in the same directory.
2.  **Run the application:**
    ```bash
    python code_manager_app.py
    ```

3.  **Configure Database:**
    * The application uses `config.ini` to store connection details.
    * Navigate to the **Database Setup/Backup** tab.
    * Enter your MySQL connection details (Host, User, Password, Database Name, e.g., `host = localhost`, `user = root`).
    * Click "**Save & Test Settings**".

4.  **Initialize Database:**
    * Click "**Setup Database & Tables**". This will create the database (if it doesn't exist) and the required tables: `created_codes` and `scanned_codes`.

5.  **Start Managing Codes:**
    * Use the **Create Code (Single/Batch)** tab to generate new codes.
    * Use the **Edit/Delete Records** tab for CRUD operations on existing codes.

## 📁 Project Structure
