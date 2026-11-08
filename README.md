# ⚡ Electricity Bill Generator – Streamlit & Python

A Python-based **Electricity Consumer Bill Generator** built with Streamlit. This application allows users to enter customer information, meter readings, electricity charges, government taxes, and previous billing details to calculate electricity bills and generate professionally formatted PDF bills.

## 🚀 Project Overview

The Electricity Bill Generator simplifies electricity bill calculation through an interactive web interface. It automatically calculates consumed units, electricity charges, taxes, total payable amounts, and late payment surcharges.

Users can customize billing information, preview bill calculations, and download the generated electricity bill in PDF format.

## ✨ Key Features

- **Customer Information Management:** Enter customer name, address, phone number, customer ID, and reference number.
- **Connection Details:** Manage connection date, meter type, tariff category, division, feeder name, and connected load.
- **Automatic Unit Calculation:** Calculate electricity consumption using previous and present meter readings and meter factor.
- **Manual Unit Entry:** Option to enter electricity consumption manually.
- **Electricity Charges:** Calculate unit costs, meter rent, service rent, fuel price adjustment, FC surcharge, and quarterly tariff adjustment.
- **Government Taxes:** Include GST, electricity duty, TV fee, income tax, and other applicable charges.
- **Bill Adjustments:** Manage arrears, previous balance, installments, subsidies, and other adjustments.
- **Late Payment Calculation:** Automatically calculate late payment surcharges.
- **Monthly Consumption History:** Add and edit up to 12 months of billing history.
- **Live Bill Preview:** View calculated units, taxes, current bill, and payable amounts.
- **PDF Generation:** Generate professionally formatted A4 electricity bills.
- **PDF Download:** Download the generated bill directly from the application.
- **Input Validation:** Validate important customer details, meter readings, dates, and charge values.

## 🛠️ Technologies Used

- Python
- Streamlit
- Pandas
- ReportLab

## 📂 Project Structure

```text
Electricity-Bill-Generator/
│
├── app.py
├── requirements.txt
└── README.md
```

## ⚙️ Installation & Setup

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/Electricity-Bill-Generator.git
```

### 2. Navigate to the Project Directory

```bash
cd Electricity-Bill-Generator
```

### 3. Create a Virtual Environment (Optional)

```bash
python -m venv venv
```

Activate the environment:

**Windows:**
```bash
venv\Scripts\activate
```

**Linux / macOS:**
```bash
source venv/bin/activate
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Run the Application

```bash
streamlit run app.py
```

The application will open in your default browser.

## 📦 Requirements

The project uses the following Python libraries:

```text
streamlit>=1.36
reportlab>=4.0
pandas>=2.0
```

## 🧮 Bill Calculation Logic

The application uses the following formulas:

**1. Electricity Units Consumed**

\[
Units = (Present\ Reading - Previous\ Reading) \times MF
\]

**2. Cost of Electricity**

\[
Electricity\ Cost = Units \times Unit\ Rate
\]

**3. Current Bill**

\[
Current\ Bill = Electricity\ Charges + Government\ Taxes
\]

**4. Total Payable Amount**

\[
Total = Current\ Bill + Arrears + Adjustments - Subsidy
\]

**5. Late Payment Surcharge**

\[
Surcharge = Total \times Late\ Payment\ Rate
\]

**6. Payable After Due Date**

\[
Payable = Total + Surcharge
\]

## 📄 PDF Bill Generation

The application generates a structured A4 PDF electricity bill containing:

- Customer and connection information
- Meter reading details
- Monthly consumption history
- Electricity charges breakdown
- Government taxes and adjustments
- Total payable amount
- Due date and late payment information

## ⚠️ Important Disclaimer

This project is an educational and demonstration application. It uses fictional utility branding and sample billing information. It is **not an official PESCO billing system**, does not connect to any electricity provider, and does not generate valid payment slips.

Actual electricity tariffs, taxes, and billing policies should be verified with the relevant electricity distribution company.

## 👨‍💻 Author

**Muhammad Idrees**

AI & Python Developer

GitHub: [Your GitHub Profile](https://github.com/your-username)

---

⭐ If you find this project useful, consider giving it a star on GitHub!
