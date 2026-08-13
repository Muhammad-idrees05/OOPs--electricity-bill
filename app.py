from __future__ import annotations

import io
import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List, Dict, Any

import pandas as pd
import streamlit as st

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.graphics.shapes import Drawing, Circle, String


# ---------------------------------------------------------------------------
# Currency helper
# ---------------------------------------------------------------------------
def format_currency(amount: float, currency: str = "PKR") -> str:
    try:
        return f"{currency} {amount:,.0f}"
    except (TypeError, ValueError):
        return f"{currency} 0"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass
class BillData:
    """Holds every field needed to render the bill."""

    # Customer info
    customer_name: str = "Muhammad idrees"
    address: str = "Fatima village mardan"
    customer_id: str = ""
    reference_number: str = ""
    phone_number: str = "0300-0000000"
    email: str = "idreeskhan@gmail.com"
    tariff_category: str = "A-1(a) Residential"
    division: str = "Mardan"
    sub_division: str = "Mardan"
    feeder_name: str = "Feeder-01"

    # Connection info
    connection_date: date = field(default_factory=lambda: date(2018, 1, 1))
    connected_load: float = 2.0
    meter_number: str = ""
    meter_type: str = "Single Phase"
    number_of_acs: int = 0
    billing_month: str = "January 2026"
    reading_date: date = field(default_factory=date.today)
    issue_date: date = field(default_factory=date.today)
    due_date: date = field(default_factory=lambda: date.today() + timedelta(days=16))

    # Meter reading
    previous_reading: float = 16760.0
    present_reading: float = 17040.0
    meter_factor: float = 1.0
    manual_units: bool = False
    manual_units_value: float = 280.0

    # Tariff / electricity charges
    unit_rate: float = 22.14
    meter_rent: float = 0.0
    service_rent: float = 0.0
    fuel_price_adjustment: float = 48.62
    fc_surcharge: float = 120.40
    quarterly_adjustment: float = 416.47
    other_electricity_charges: float = 0.0

    # Taxes / government charges
    electricity_duty: float = 99.0
    tv_fee: float = 35.0
    gst: float = 1162.0
    income_tax: float = 0.0
    extra_tax: float = 0.0
    further_tax: float = 0.0
    retailer_tax: float = 0.0
    other_taxes: float = 9.73

    # Previous / current amounts
    arrears: float = 0.0
    previous_balance: float = 0.0
    bill_adjustment: float = 0.0
    installment: float = 0.0
    subsidy: float = 0.0
    other_adjustment: float = 0.0
    late_payment_rate: float = 0.10  # e.g. 10% surcharge if paid after due date

    # Misc
    currency: str = "PKR"
    notice: str = "You are better service"

    # History table: list of dicts {Month, Units, Bill, Payment}
    history: List[Dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Calculator
# ---------------------------------------------------------------------------
class BillCalculator:
    """All bill math lives here so formulas stay transparent & easy to edit."""

    @staticmethod
    def units_consumed(data: BillData) -> float:
        if data.manual_units:
            return max(data.manual_units_value, 0.0)
        units = (data.present_reading - data.previous_reading) * data.meter_factor
        return max(units, 0.0)

    @staticmethod
    def cost_of_electricity(units: float, data: BillData) -> float:
        return units * data.unit_rate

    @staticmethod
    def electricity_subtotal(units: float, data: BillData) -> float:
        cost = BillCalculator.cost_of_electricity(units, data)
        return (
            cost
            + data.meter_rent
            + data.service_rent
            + data.fuel_price_adjustment
            + data.fc_surcharge
            + data.quarterly_adjustment
            + data.other_electricity_charges
        )

    @staticmethod
    def tax_subtotal(data: BillData) -> float:
        return (
            data.electricity_duty
            + data.tv_fee
            + data.gst
            + data.income_tax
            + data.extra_tax
            + data.further_tax
            + data.retailer_tax
            + data.other_taxes
        )

    @staticmethod
    def current_bill(units: float, data: BillData) -> float:
        return BillCalculator.electricity_subtotal(units, data) + BillCalculator.tax_subtotal(data)

    @staticmethod
    def total_charges(units: float, data: BillData) -> float:
        current_bill = BillCalculator.current_bill(units, data)
        return (
            current_bill
            + data.arrears
            + data.previous_balance
            + data.bill_adjustment
            + data.installment
            - data.subsidy
            + data.other_adjustment
        )

    @staticmethod
    def payable_within_due_date(units: float, data: BillData) -> float:
        return BillCalculator.total_charges(units, data)

    @staticmethod
    def late_payment_surcharge(units: float, data: BillData) -> float:
        return BillCalculator.payable_within_due_date(units, data) * data.late_payment_rate

    @staticmethod
    def payable_after_due_date(units: float, data: BillData) -> float:
        return BillCalculator.payable_within_due_date(units, data) + BillCalculator.late_payment_surcharge(
            units, data
        )

    @classmethod
    def summary(cls, data: BillData) -> Dict[str, float]:
        units = cls.units_consumed(data)
        return {
            "units": units,
            "cost_of_electricity": cls.cost_of_electricity(units, data),
            "electricity_subtotal": cls.electricity_subtotal(units, data),
            "tax_subtotal": cls.tax_subtotal(data),
            "current_bill": cls.current_bill(units, data),
            "total_charges": cls.total_charges(units, data),
            "payable_within_due_date": cls.payable_within_due_date(units, data),
            "late_payment_surcharge": cls.late_payment_surcharge(units, data),
            "payable_after_due_date": cls.payable_after_due_date(units, data),
        }


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------
class BillValidator:
    @staticmethod
    def validate(data: BillData) -> List[str]:
        errors: List[str] = []

        if not data.customer_name or not data.customer_name.strip():
            errors.append("Customer name is required.")

        if not data.meter_number or not data.meter_number.strip():
            errors.append("Meter number is required.")

        if not data.billing_month or not data.billing_month.strip():
            errors.append("Billing month is required.")

        if not data.manual_units and data.present_reading < data.previous_reading:
            errors.append("Present reading must be greater than or equal to previous reading.")

        if data.unit_rate <= 0:
            errors.append("Unit rate must be a positive number.")

        if data.due_date < data.issue_date:
            errors.append("Due date cannot be before the issue date.")

        if data.issue_date < data.reading_date:
            errors.append("Issue date cannot be before the reading date.")

        charge_fields = {
            "Meter rent": data.meter_rent,
            "Service rent": data.service_rent,
            "Fuel price adjustment": data.fuel_price_adjustment,
            "FC surcharge": data.fc_surcharge,
            "Quarterly adjustment": data.quarterly_adjustment,
            "Other electricity charges": data.other_electricity_charges,
            "Electricity duty": data.electricity_duty,
            "TV fee": data.tv_fee,
            "GST": data.gst,
            "Income tax": data.income_tax,
            "Extra tax": data.extra_tax,
            "Further tax": data.further_tax,
            "Retailer tax": data.retailer_tax,
            "Other taxes": data.other_taxes,
        }
        for name, value in charge_fields.items():
            if value < 0:
                errors.append(f"{name} cannot be negative.")

        return errors


# ---------------------------------------------------------------------------
# PDF style manager
# ---------------------------------------------------------------------------
class PDFStyleManager:
    """Central place for the bill's color palette & paragraph styles."""

    DEEP_BLUE = colors.HexColor("#0B3D6E")
    LIGHT_BLUE = colors.HexColor("#DCEBFA")
    SOFT_CYAN = colors.HexColor("#EEF14F")
    LIGHT_GRAY = colors.HexColor("#F2F2F2")
    MID_GRAY = colors.HexColor("#CCCCCC")
    PINK = colors.HexColor("#EDBABA")
    YELLOW = colors.HexColor("#DEC36D")
    WHITE = colors.white
    WATERMARK_RED = colors.HexColor("#C0392B")
    TOTAL_GREEN = colors.HexColor("#1E7A46")

    def __init__(self):
        base = getSampleStyleSheet()

        self.title = ParagraphStyle(
            "DemoTitle", parent=base["Heading1"], fontName="Helvetica-Bold",
            fontSize=15, textColor=self.DEEP_BLUE, alignment=TA_CENTER, spaceAfter=1,
        )
        self.subtitle = ParagraphStyle(
            "DemoSubtitle", parent=base["Normal"], fontName="Helvetica",
            fontSize=8, textColor=self.DEEP_BLUE, alignment=TA_CENTER, spaceAfter=1,
        )
        self.watermark = ParagraphStyle(
            "DemoWatermark", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=9.5, textColor=self.WATERMARK_RED, alignment=TA_CENTER,
            spaceAfter=3, spaceBefore=1,
        )
        self.corner_label = ParagraphStyle(
            "CornerLabel", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=6.5, textColor=self.DEEP_BLUE, alignment=TA_RIGHT,
        )
        self.section_header = ParagraphStyle(
            "SectionHeader", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=8, textColor=self.DEEP_BLUE, alignment=TA_CENTER,
        )
        self.cell_label = ParagraphStyle(
            "CellLabel", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=6, textColor=self.DEEP_BLUE, alignment=TA_CENTER,
        )
        self.cell_value = ParagraphStyle(
            "CellValue", parent=base["Normal"], fontName="Helvetica",
            fontSize=7, alignment=TA_CENTER,
        )
        self.cell_value_left = ParagraphStyle(
            "CellValueLeft", parent=base["Normal"], fontName="Helvetica",
            fontSize=7, alignment=TA_LEFT,
        )
        self.small_left = ParagraphStyle(
            "SmallLeft", parent=base["Normal"], fontName="Helvetica",
            fontSize=6.5, alignment=TA_LEFT, textColor=colors.HexColor("#333333"),
        )
        self.footer = ParagraphStyle(
            "Footer", parent=base["Normal"], fontName="Helvetica-Oblique",
            fontSize=6.5, textColor=colors.HexColor("#555555"), alignment=TA_CENTER,
        )
        self.stub = ParagraphStyle(
            "Stub", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=9, textColor=self.DEEP_BLUE, alignment=TA_CENTER,
        )


# ---------------------------------------------------------------------------
# PDF generator — single page, structurally mirrors a typical printed bill
# ---------------------------------------------------------------------------
class PDFBillGenerator:
    PAGE_W, PAGE_H = A4
    FULL_W = 515  # usable content width in points (A4 minus 14mm margins)

    def __init__(self, data: BillData):
        self.data = data
        self.styles = PDFStyleManager()
        self.summary = BillCalculator.summary(data)

    # -- fictional logo -----------------------------------------------------
    def _fictional_logo(self) -> Drawing:
        d = Drawing(35, 35)
        d.add(Circle(18, 18, 16, fillColor=self.styles.SOFT_CYAN, strokeColor=self.styles.DEEP_BLUE, strokeWidth=1.8))
        d.add(Circle(18, 18, 9, fillColor=self.styles.WHITE, strokeColor=self.styles.DEEP_BLUE, strokeWidth=1))
        d.add(String(17, 14.5, "Pesco", fontName="Helvetica-Bold", fontSize=8, fillColor=self.styles.DEEP_BLUE, textAnchor="middle"))
        return d

    # -- header row: logo + company name + due date callout -------------
    def _build_header(self) -> Table:
        s = self.styles
        d = self.data
        logo = self._fictional_logo()

        name_block = [
            Paragraph("POWER SUPPLY COMPANY", s.title),
            Paragraph("FICTIONAL UTILITY &mdash; ELECTRICITY CONSUMER BILL", s.subtitle),
        ]
        due_block = Paragraph(
            f"MARDAN ID No.<br/>{d.customer_id or 'MARDAN-0000000000'}", s.corner_label
        )

        header = Table(
            [[logo, name_block, due_block]],
            colWidths=[42, self.FULL_W - 42 - 110, 110],
        )
        header.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (1, 0), (1, 0), "CENTER"),
                    ("ALIGN", (2, 0), (2, 0), "RIGHT"),
                ]
            )
        )
        return header

    # -- top info grid (mirrors the reference's stacked label/value grid) --
    def _build_top_grid(self) -> Table:
        d = self.data
        s = self.styles

        def lbl(text):
            return Paragraph(text, s.cell_label)

        def val(text):
            return Paragraph(str(text), s.cell_value)

        col_w = self.FULL_W / 6.0
        rows = [
            [lbl("CONNECTION DATE"), lbl("CONNECTED LOAD"), lbl("BILL MONTH"), lbl("READING DATE"), lbl("ISSUE DATE"), lbl("DUE DATE")],
            [
                val(d.connection_date.strftime("%d %b %y")),
                val(f"{d.connected_load:g}"),
                val(d.billing_month),
                val(d.reading_date.strftime("%d %b %y")),
                val(d.issue_date.strftime("%d %b %y")),
                val(d.due_date.strftime("%d %b %y")),
            ],
            [lbl("CUSTOMER ID"), lbl("TARIFF"), lbl("LOAD"), lbl("DIVISION"), lbl("SUB DIVISION"), lbl("FEEDER NAME")],
            [
                val(d.customer_id or "MARDAN-0000000000"),
                val(d.tariff_category),
                val(f"{d.connected_load:g} kW"),
                val(d.division),
                val(d.sub_division),
                val(d.feeder_name),
            ],
            [lbl("REFERENCE NO"), lbl("METER TYPE"), lbl("NO OF ACs"), lbl(""), lbl(""), lbl("")],
            [
                val(d.reference_number or "MARDAN-REF-0000"),
                val(d.meter_type),
                val(d.number_of_acs),
                "", "", "",
            ],
        ]
        table = Table(rows, colWidths=[col_w] * 6)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), self.styles.LIGHT_BLUE),
                    ("BACKGROUND", (0, 2), (-1, 2), self.styles.LIGHT_BLUE),
                    ("BACKGROUND", (0, 4), (-1, 4), self.styles.LIGHT_BLUE),
                    ("SPAN", (3, 4), (5, 4)),
                    ("SPAN", (3, 5), (5, 5)),
                    ("GRID", (0, 0), (-1, -1), 0.5, self.styles.MID_GRAY),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )
        return table

    # -- customer block (left) --------------------------------------------
    def _build_customer_block(self):
        d = self.data
        s = self.styles
        content = [
            Paragraph("<b>NAME &amp; ADDRESS</b>", s.cell_label),
            Spacer(1, 2),
            Paragraph(f"{d.customer_name}<br/>{d.address}<br/>Ph: {d.phone_number}", s.cell_value_left),
            Spacer(1, 4),
            Paragraph(
                f"<b>Meter No:</b> {d.meter_number or 'MARDAN-MTR-000'}<br/>"
                f"<b>Reference No:</b> {d.reference_number or 'MARDAN-REF-000'}<br/>"
                f"<b>No. of ACs:</b> {d.number_of_acs}",
                s.cell_value_left,
            ),
            Spacer(1, 5),
            Paragraph(f"<i>{d.notice}</i>", s.small_left),
        ]
        return content

    # -- monthly history table (right) -------------------------------------
    def _build_history_table(self) -> Table:
        d = self.data
        s = self.styles
        header = [Paragraph("MONTH", s.section_header), Paragraph("UNITS", s.section_header),
                  Paragraph("BILL", s.section_header), Paragraph("PAYMENT", s.section_header)]
        rows = [header]
        for row in d.history[:12]:
            rows.append(
                [
                    Paragraph(str(row.get("Month", "")), s.cell_value),
                    Paragraph(f"{row.get('Units', 0):,.0f}", s.cell_value),
                    Paragraph(f"{row.get('Bill', 0):,.0f}", s.cell_value),
                    Paragraph(f"{row.get('Payment', 0):,.0f}", s.cell_value),
                ]
            )
        col_w = 85
        table = Table(rows, colWidths=[col_w] * 4)
        style = [
            ("BACKGROUND", (0, 0), (-1, 0), self.styles.SOFT_CYAN),
            ("GRID", (0, 0), (-1, -1), 0.5, self.styles.MID_GRAY),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 1.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
        ]
        for i in range(1, len(rows)):
            if i % 2 == 0:
                style.append(("BACKGROUND", (0, i), (-1, i), self.styles.LIGHT_GRAY))
        table.setStyle(TableStyle(style))
        return table

    # -- customer + history side-by-side row --------------------------------
    def _build_customer_history_row(self) -> Table:
        left = self._build_customer_block()
        right = self._build_history_table()
        combined = Table([[left, right]], colWidths=[self.FULL_W - 85 * 4 - 6, 85 * 4])
        combined.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("GRID", (0, 0), (0, 0), 0.5, self.styles.MID_GRAY),
                    ("TOPPADDING", (0, 0), (0, 0), 4),
                    ("LEFTPADDING", (0, 0), (0, 0), 5),
                ]
            )
        )
        return combined

    # -- meter reading table -----------------------------------------------
    def _build_meter_section(self) -> Table:
        d = self.data
        s = self.styles
        units = self.summary["units"]
        header = ["METER NO", "PREVIOUS READING", "PRESENT READING", "MF", "UNITS", "STATUS"]
        row = [
            d.meter_number or "MARDAN-MTR-000",
            f"{d.previous_reading:,.0f}",
            f"{d.present_reading:,.0f}",
            f"{d.meter_factor:g}",
            f"{units:,.0f}",
            "Normal",
        ]
        col_w = self.FULL_W / 6.0
        table = Table([header, row], colWidths=[col_w] * 6)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), self.styles.DEEP_BLUE),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 7),
                    ("GRID", (0, 0), (-1, -1), 0.5, self.styles.MID_GRAY),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        return table

    # -- three-column charges / totals block --------------------------------
    def _build_three_column_charges(self) -> Table:
        d = self.data
        s = self.summary
        cur = d.currency
        units = s["units"]

        elec_rows = [
            [Paragraph("ELECTRICITY CHARGES", self.styles.section_header), ""],
            ["Units Consumed", f"{units:,.0f}"],
            ["Cost of Electricity", f"{s['cost_of_electricity']:,.0f}"],
            ["Meter Rent", f"{d.meter_rent:,.0f}"],
            ["Service Rent", f"{d.service_rent:,.0f}"],
            ["Fuel Price Adj.", f"{d.fuel_price_adjustment:,.0f}"],
            ["FC Surcharge", f"{d.fc_surcharge:,.0f}"],
            ["Qtr Tariff Adj.", f"{d.quarterly_adjustment:,.0f}"],
            ["Other Charges", f"{d.other_electricity_charges:,.0f}"],
            ["TOTAL", f"{s['electricity_subtotal']:,.0f}"],
        ]
        tax_rows = [
            [Paragraph("GOVT CHARGES", self.styles.section_header), ""],
            ["Electricity Duty", f"{d.electricity_duty:,.0f}"],
            ["TV Fee", f"{d.tv_fee:,.0f}"],
            ["GST", f"{d.gst:,.0f}"],
            ["Income Tax", f"{d.income_tax:,.0f}"],
            ["Extra Tax", f"{d.extra_tax:,.0f}"],
            ["Further Tax", f"{d.further_tax:,.0f}"],
            ["Retailer Tax", f"{d.retailer_tax:,.0f}"],
            ["Other Tax", f"{d.other_taxes:,.0f}"],
            ["TOTAL", f"{s['tax_subtotal']:,.0f}"],
        ]
        total_rows = [
            [Paragraph("TOTAL CHARGES", self.styles.section_header), ""],
            ["Arrears/Age", f"{d.arrears:,.0f}"],
            ["Current Bill", f"{s['current_bill']:,.0f}"],
            ["Bill Adjustment", f"{d.bill_adjustment:,.0f}"],
            ["Installment", f"{d.installment:,.0f}"],
            ["Subsidy", f"-{d.subsidy:,.0f}"],
            ["PAYABLE WITHIN\nDUE DATE", f"{s['payable_within_due_date']:,.0f}"],
            ["L.P. Surcharge", f"{s['late_payment_surcharge']:,.0f}"],
            ["PAYABLE AFTER\nDUE DATE", f"{s['payable_after_due_date']:,.0f}"],
            ["", ""],
        ]

        def make_col(rows, header_bg, highlight_rows=None):
            highlight_rows = highlight_rows or []
            t = Table(rows, colWidths=[95, 65])
            style = [
                ("SPAN", (0, 0), (1, 0)),
                ("BACKGROUND", (0, 0), (-1, 0), header_bg),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("FONTSIZE", (0, 0), (-1, -1), 6.3),
                ("GRID", (0, 0), (-1, -1), 0.5, self.styles.MID_GRAY),
                ("ALIGN", (1, 1), (1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ]
            for r in highlight_rows:
                style.append(("BACKGROUND", (0, r), (-1, r), self.styles.SOFT_CYAN))
                style.append(("FONTNAME", (0, r), (-1, r), "Helvetica-Bold"))
            t.setStyle(TableStyle(style))
            return t

        left = make_col(elec_rows, self.styles.LIGHT_BLUE, highlight_rows=[len(elec_rows) - 1])
        mid = make_col(tax_rows, self.styles.PINK, highlight_rows=[len(tax_rows) - 1])
        right = make_col(total_rows, self.styles.SOFT_CYAN, highlight_rows=[6, 8])

        outer = Table([[left, mid, right]], colWidths=[160, 160, 195])
        outer.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
        return outer

    # -- bill calculation summary box ---------------------------------------
    def _build_calculation_box(self) -> Table:
        d = self.data
        s = self.summary
        units = s["units"]
        text = (
            f"<b>BILL CALCULATION </b><br/>"
            f"Tariff Rate &times; Units = {d.unit_rate:g} &times; {units:,.0f} = "
            f"{format_currency(s['cost_of_electricity'], d.currency)}<br/>"
            f"Fuel Price Adjustment: {format_currency(d.fuel_price_adjustment, d.currency)}"
        )
        p = Paragraph(text, self.styles.small_left)
        t = Table([[p]], colWidths=[self.FULL_W])
        t.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.5, self.styles.MID_GRAY),
                    ("BACKGROUND", (0, 0), (-1, -1), self.styles.LIGHT_GRAY),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        return t

    # -- prominent payable amount banner -------------------------------------
    def _build_payable_banner(self) -> Table:
        s = self.summary
        d = self.data
        t = Table(
            [["PAYABLE AFTER DUE DATE", format_currency(s["payable_after_due_date"], d.currency)]],
            colWidths=[self.FULL_W * 0.62, self.FULL_W * 0.38],
        )
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), self.styles.TOTAL_GREEN),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 11),
                    ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                    ("ALIGN", (0, 0), (0, 0), "LEFT"),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        return t

    # -- tear-off bottom stub (structural echo, no real branding) -----------
    def _build_stub(self) -> Table:
        d = self.data
        s = self.styles
        cut_line = Table([[Paragraph("- - - - - - - - - - - - - - -  CUT HERE  - - - - - - - - - - - - - - -", s.footer)]], colWidths=[self.FULL_W])
        cut_line.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))

        stub = Table(
            [
                [Paragraph(" POWER SUPPLY COMPANY &mdash; ELECTRICITY CONSUMER BILL ", s.stub), ""],
                [Paragraph("Fictional stub &mdash; not a real payment slip", s.footer),
                 Paragraph(f"<b>Customer ID:</b> {d.customer_id or 'MARDAN-0000000000'}", s.cell_value)],
            ],
            colWidths=[self.FULL_W * 0.65, self.FULL_W * 0.35],
        )
        stub.setStyle(
            TableStyle(
                [
                    ("SPAN", (0, 0), (1, 0)),
                    ("ALIGN", (0, 0), (1, 0), "CENTER"),
                    ("BOX", (0, 0), (-1, -1), 0.5, self.styles.MID_GRAY),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("ALIGN", (1, 1), (1, 1), "RIGHT"),
                ]
            )
        )
        return Table([[cut_line], [Spacer(1, 3)], [stub]], colWidths=[self.FULL_W])

    # -- page decoration (diagonal watermark + slim footer) -----------------
    def _on_page(self, canvas: pdfcanvas.Canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica-Bold", 40)
        canvas.setFillColor(colors.Color(0.85, 0.1, 0.1, alpha=0.09))
        canvas.translate(self.PAGE_W / 2, self.PAGE_H / 2)
        canvas.rotate(45)
        canvas.drawCentredString(0, 0, "PESCO")
        canvas.restoreState()

        canvas.saveState()
        canvas.setFont("Helvetica-Bold", 7.5)
        canvas.setFillColor(self.styles.WATERMARK_RED)
        canvas.drawCentredString(self.PAGE_W / 2, self.PAGE_H - 10, " PESCO OFFICIAL BILL")
        canvas.restoreState()

        canvas.saveState()
        canvas.setFont("Helvetica", 6)
        canvas.setFillColor(colors.HexColor("#777777"))
        canvas.drawCentredString(
            self.PAGE_W / 2, 12,
            "Peshawar Power Supply company."
        )
        canvas.restoreState()

    # -- public build method -------------------------------------------
    def generate(self) -> bytes:
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            topMargin=16 * mm,
            bottomMargin=12 * mm,
            leftMargin=14 * mm,
            rightMargin=14 * mm,
            title=" Electricity Bill",
        )

        elements: List = [
            self._build_header(),
            Spacer(1, 3),
            self._build_top_grid(),
            Spacer(1, 4),
            self._build_customer_history_row(),
            Spacer(1, 4),
            self._build_meter_section(),
            Spacer(1, 4),
            self._build_three_column_charges(),
            Spacer(1, 4),
            self._build_calculation_box(),
            Spacer(1, 4),
            self._build_payable_banner(),
            Spacer(1, 6),
            self._build_stub(),
        ]

        doc.build(elements, onFirstPage=self._on_page, onLaterPages=self._on_page)
        buf.seek(0)
        return buf.read()


# ---------------------------------------------------------------------------
# Sample / default history
# ---------------------------------------------------------------------------
def default_history() -> List[Dict[str, Any]]:
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    rng = random.Random(42)
    rows = []
    for m in months:
        units = rng.randint(120, 300)
        bill = round(units * 22.14 + rng.randint(500, 1200), 0)
        rows.append({"Month": f"{m}25", "Units": units, "Bill": bill, "Payment": bill})
    return rows


def random_id(prefix: str, digits: int = 10) -> str:
    rng = random.Random()
    return f"{prefix}-{''.join(str(rng.randint(0, 9)) for _ in range(digits))}"


# ---------------------------------------------------------------------------
# Streamlit UI
# ---------------------------------------------------------------------------
class StreamlitUI:
    def __init__(self):
        st.set_page_config(
            page_title="Electricity Bill Generator",
            page_icon="",
            layout="wide",
        )
        if "bill_data" not in st.session_state:
            st.session_state.bill_data = BillData(
                customer_id=random_id("MARDAN-CUST"),
                reference_number=random_id("MARDAN-REF", 8),
                meter_number=random_id("MARDAN-MTR", 6),
                history=default_history(),
            )
        if "history_df" not in st.session_state:
            st.session_state.history_df = pd.DataFrame(st.session_state.bill_data.history)
        if "pdf_bytes" not in st.session_state:
            st.session_state.pdf_bytes = None

    # ------------------------------------------------------------------
    def run(self):
        st.title("Electricity Consumer Bill Generator")

        data = st.session_state.bill_data

        with st.expander("Customer Information", expanded=True):
            self._customer_section(data)

        with st.expander(" Connection Information", expanded=True):
            self._connection_section(data)

        with st.expander("Meter Reading", expanded=True):
            self._meter_section(data)

        with st.expander("Tariff & Electricity Charges", expanded=False):
            self._electricity_charges_section(data)

        with st.expander("Taxes / Government Charges", expanded=False):
            self._tax_section(data)

        with st.expander("Previous / Current Amounts", expanded=False):
            self._adjustments_section(data)

        with st.expander("Monthly Consumption History (up to 12 months)", expanded=False):
            self._history_section(data)

        with st.expander("Optional Notice & Currency", expanded=False):
            self._notice_section(data)

        st.divider()
        self._action_buttons(data)

    # ------------------------------------------------------------------
    def _customer_section(self, d: BillData):
        c1, c2 = st.columns(2)
        with c1:
            d.customer_name = st.text_input("Customer Name", d.customer_name)
            d.address = st.text_area("Address", d.address, height=70)
            d.customer_id = st.text_input("Customer ID", d.customer_id)
            d.reference_number = st.text_input("Reference Number", d.reference_number)
            d.phone_number = st.text_input("Phone Number", d.phone_number)
        with c2:
            d.email = st.text_input("Email", d.email)
            d.tariff_category = st.selectbox(
                "Tariff Category",
                ["A-1(a) Residential", "A-2 Commercial", "B Industrial", "C Bulk Supply", "Other"],
                index=0 if d.tariff_category not in
                ["A-2 Commercial", "B Industrial", "C Bulk Supply", "Other"] else
                ["A-1(a) Residential", "A-2 Commercial", "B Industrial", "C Bulk Supply", "Other"].index(d.tariff_category),
            )
            d.division = st.text_input("Division", d.division)
            d.sub_division = st.text_input("Sub-Division", d.sub_division)
            d.feeder_name = st.text_input("Feeder Name", d.feeder_name)

    def _connection_section(self, d: BillData):
        c1, c2, c3 = st.columns(3)
        with c1:
            d.connection_date = st.date_input("Connection Date", d.connection_date)
            d.connected_load = st.number_input("Connected Load (kW)", value=float(d.connected_load), min_value=0.0, step=0.5)
            d.meter_number = st.text_input("Meter Number", d.meter_number)
        with c2:
            d.meter_type = st.selectbox(
                "Meter Type", ["Single Phase", "Three Phase", "Smart Meter"],
                index=["Single Phase", "Three Phase", "Smart Meter"].index(d.meter_type)
                if d.meter_type in ["Single Phase", "Three Phase", "Smart Meter"] else 0,
            )
            d.number_of_acs = st.number_input("Number of ACs", value=int(d.number_of_acs), min_value=0, step=1)
            d.billing_month = st.text_input("Billing Month", d.billing_month)
        with c3:
            d.reading_date = st.date_input("Reading Date", d.reading_date)
            d.issue_date = st.date_input("Issue Date", d.issue_date)
            d.due_date = st.date_input("Due Date", d.due_date)

    def _meter_section(self, d: BillData):
        c1, c2, c3 = st.columns(3)
        with c1:
            d.previous_reading = st.number_input("Previous Reading", value=float(d.previous_reading), min_value=0.0, step=1.0)
        with c2:
            d.present_reading = st.number_input("Present Reading", value=float(d.present_reading), min_value=0.0, step=1.0)
        with c3:
            d.meter_factor = st.number_input("Meter Factor", value=float(d.meter_factor), min_value=0.0, step=0.1)

        d.manual_units = st.checkbox("Enter units manually", value=d.manual_units)
        if d.manual_units:
            d.manual_units_value = st.number_input("Units Consumed (manual)", value=float(d.manual_units_value), min_value=0.0)
            units = d.manual_units_value
        else:
            units = BillCalculator.units_consumed(d)
            st.info(f"Calculated Units Consumed: **{units:,.0f}**  (= (Present − Previous) × MF)")

    def _electricity_charges_section(self, d: BillData):
        c1, c2 = st.columns(2)
        with c1:
            d.unit_rate = st.number_input("Unit Rate", value=float(d.unit_rate), min_value=0.01, step=0.1)
            d.meter_rent = st.number_input("Meter Rent", value=float(d.meter_rent), min_value=0.0)
            d.service_rent = st.number_input("Service Rent", value=float(d.service_rent), min_value=0.0)
            d.fuel_price_adjustment = st.number_input("Fuel Price Adjustment", value=float(d.fuel_price_adjustment))
        with c2:
            d.fc_surcharge = st.number_input("FC Surcharge", value=float(d.fc_surcharge))
            d.quarterly_adjustment = st.number_input("Quarterly Tariff Adjustment", value=float(d.quarterly_adjustment))
            d.other_electricity_charges = st.number_input("Other Electricity Charges", value=float(d.other_electricity_charges))

        units = BillCalculator.units_consumed(d)
        cost = BillCalculator.cost_of_electricity(units, d)
        subtotal = BillCalculator.electricity_subtotal(units, d)
        st.success(f"Cost of Electricity: {format_currency(cost, d.currency)}  |  Electricity Subtotal: {format_currency(subtotal, d.currency)}")

    def _tax_section(self, d: BillData):
        c1, c2 = st.columns(2)
        with c1:
            d.electricity_duty = st.number_input("Electricity Duty", value=float(d.electricity_duty), min_value=0.0)
            d.tv_fee = st.number_input("TV Fee", value=float(d.tv_fee), min_value=0.0)
            d.gst = st.number_input("GST", value=float(d.gst), min_value=0.0)
            d.income_tax = st.number_input("Income Tax", value=float(d.income_tax), min_value=0.0)
        with c2:
            d.extra_tax = st.number_input("Extra Tax", value=float(d.extra_tax), min_value=0.0)
            d.further_tax = st.number_input("Further Tax", value=float(d.further_tax), min_value=0.0)
            d.retailer_tax = st.number_input("Retailer Tax", value=float(d.retailer_tax), min_value=0.0)
            d.other_taxes = st.number_input("Other Taxes", value=float(d.other_taxes), min_value=0.0)

        st.success(f"Tax Subtotal: {format_currency(BillCalculator.tax_subtotal(d), d.currency)}")

    def _adjustments_section(self, d: BillData):
        c1, c2 = st.columns(2)
        with c1:
            d.arrears = st.number_input("Arrears", value=float(d.arrears))
            d.previous_balance = st.number_input("Previous Balance", value=float(d.previous_balance))
            d.bill_adjustment = st.number_input("Bill Adjustment", value=float(d.bill_adjustment))
        with c2:
            d.installment = st.number_input("Installment", value=float(d.installment))
            d.subsidy = st.number_input("Subsidy", value=float(d.subsidy), min_value=0.0)
            d.other_adjustment = st.number_input("Other Adjustment", value=float(d.other_adjustment))
        d.late_payment_rate = st.slider("Late Payment Surcharge Rate", 0.0, 0.5, float(d.late_payment_rate), step=0.01, format="%.2f")

    def _history_section(self, d: BillData):
        st.caption("Edit the monthly history table below (used for the consumption history section of the PDF).")
        edited = st.data_editor(
            st.session_state.history_df,
            num_rows="dynamic",
            use_container_width=True,
            key="history_editor",
        )
        st.session_state.history_df = edited
        d.history = edited.to_dict("records")

    def _notice_section(self, d: BillData):
        d.currency = st.text_input("Currency Code", d.currency)
        d.notice = st.text_area("Notice / Custom Message", d.notice, height=70)

    # ------------------------------------------------------------------
    def _action_buttons(self, d: BillData):
        col1, col2, col3 = st.columns(3)
        calc_clicked = col1.button(" Calculate Bill", use_container_width=True)
        gen_clicked = col2.button("Generate PDF", use_container_width=True, type="primary")
        reset_clicked = col3.button("Reset Form", use_container_width=True)

        if reset_clicked:
            for key in ["bill_data", "history_df", "pdf_bytes"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

        errors = BillValidator.validate(d)

        if calc_clicked or gen_clicked:
            if errors:
                for e in errors:
                    st.error(e)
            else:
                self._show_preview(d)

        if gen_clicked and not errors:
            generator = PDFBillGenerator(d)
            st.session_state.pdf_bytes = generator.generate()
            st.success("PDF generated successfully ")

        if st.session_state.pdf_bytes:
            st.download_button(
                label=" Download Bill PDF",
                data=st.session_state.pdf_bytes,
                file_name=f"electricity_bill_{d.customer_id or 'sample'}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

    def _show_preview(self, d: BillData):
        summary = BillCalculator.summary(d)
        st.subheader(" Live Bill Summary (Preview)")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Customer", d.customer_name)
            st.metric("Units Consumed", f"{summary['units']:,.0f}")
        with c2:
            st.metric("Current Bill", format_currency(summary["current_bill"], d.currency))
            st.metric("Tax Subtotal", format_currency(summary["tax_subtotal"], d.currency))
        with c3:
            st.metric("Total Charges", format_currency(summary["total_charges"], d.currency))
            st.metric("Due Date", d.due_date.strftime("%d %b %Y"))

        st.markdown(
            f"###  Payable Within Due Date: {format_currency(summary['payable_within_due_date'], d.currency)}"
        )
        st.markdown(
            f"###  Payable After Due Date: {format_currency(summary['payable_after_due_date'], d.currency)}"
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    ui = StreamlitUI()
    ui.run()


if __name__ == "__main__":
    main()