import io, os, json
from xml.sax.saxutils import escape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.units import mm
from reportlab.graphics.barcode import code128
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF
import qrcode
from .models import Client, Site, Employee, InvoiceLine, Product, Timesheet, Setting
from .payroll import money

NAVY=colors.HexColor('#112246'); BLUE=colors.HexColor('#2674e9'); GREY=colors.HexColor('#56647c')

def prop(db,key,default=''):
    s=db.get(Setting,key)
    return s.value if s else os.getenv(key.upper(),default)

def styles():
    s=getSampleStyleSheet()
    s.add(ParagraphStyle(name='BrandTitle',parent=s['Title'],fontName='Helvetica-Bold',fontSize=20,textColor=NAVY,spaceAfter=10))
    s.add(ParagraphStyle(name='MetaSmall',fontName='Helvetica',fontSize=9,leading=13,textColor=GREY))
    s.add(ParagraphStyle(name='SmallRight',fontName='Helvetica',fontSize=9,alignment=TA_RIGHT))
    return s

def P(t,sty): return Paragraph(escape(str(t or '')).replace('\n','<br/>'),sty)

def document(title,parts):
    out=io.BytesIO()
    doc=SimpleDocTemplate(out,pagesize=(210*mm,297*mm),rightMargin=19*mm,leftMargin=19*mm,topMargin=16*mm,bottomMargin=16*mm,title=title)
    def footer(c,d):
        c.setFont('Helvetica',8);c.setFillColor(GREY);c.drawString(19*mm,12*mm,'Crystal Cleaning Operations Hub  |  AUD');c.drawRightString(190*mm,12*mm,f'Page {d.page}')
    doc.build(parts,onFirstPage=footer,onLaterPages=footer)
    return out.getvalue()

def table(rows,widths=None):
    t=Table([[str(v) for v in row] for row in rows],colWidths=widths,repeatRows=1,hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),NAVY),('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f1f5fb')]),('GRID',(0,0),(-1,-1),.25,colors.HexColor('#dbe4ef')),('BOTTOMPADDING',(0,0),(-1,-1),10),('TOPPADDING',(0,0),(-1,-1),10),('FONTSIZE',(0,0),(-1,-1),8)]))
    return t

def invoice_pdf(db,invoice):
    s=styles();cl=db.get(Client,invoice.client_id);site=db.get(Site,invoice.site_id) if invoice.site_id else None
    lines=db.query(InvoiceLine).filter_by(invoice_id=invoice.id).all()
    parts=[P(prop(db,'company_name','Crystal Cleaning'),s['BrandTitle']),P(f"ABN: {prop(db,'company_abn')} | {prop(db,'company_address')}",s['MetaSmall']),Spacer(1,12),P('TAX INVOICE',s['Heading1']),P(f'Invoice: {invoice.number}  |  Issued: {invoice.issue_date}  |  Due: {invoice.due_date}',s['Normal']),Spacer(1,8),P(f'Bill to: {cl.name}',s['Heading3']),P(cl.address,s['Normal'])]
    if site:parts.append(P(f'Site: {site.name} | {site.address}',s['Normal']))
    parts+=[Spacer(1,16),table([['Description','Qty','Unit price','Total']]+[[l.description,f'{l.quantity:g}',f'${l.unit_price:,.2f}',f'${money(l.quantity*l.unit_price):,.2f}'] for l in lines],[93*mm,20*mm,28*mm,32*mm]),Spacer(1,12),P(f'Subtotal: ${invoice.subtotal:,.2f}',s['SmallRight']),P(f'GST: ${invoice.gst:,.2f}',s['SmallRight']),P(f'TOTAL: ${invoice.total:,.2f}',s['Heading2']),P(f'Paid: ${invoice.paid:,.2f}  |  Balance: ${money(invoice.total-invoice.paid):,.2f}',s['Normal']),Spacer(1,16),P(f"Payment BSB: {prop(db,'company_bsb')} | Account: {prop(db,'company_account')}",s['MetaSmall'])]
    return document(invoice.number,parts)

def payslip_pdf(db,item,run):
    s=styles();emp=db.get(Employee,item.employee_id);details=json.loads(item.details)
    parts=[P(prop(db,'company_name','Crystal Cleaning'),s['BrandTitle']),P(f"ABN: {prop(db,'company_abn')}",s['MetaSmall']),Spacer(1,12),P('PAY SLIP — PAYROLL REVIEW REQUIRED',s['Heading1']),P(f'Employee: {emp.name} ({emp.employee_code})',s['Heading3']),P(f'Pay period: {run.period_start} to {run.period_end} | Payment date: {run.pay_date}',s['Normal']),Spacer(1,12)]
    rows=[['Earnings / allowance','Hours','Rate (AUD)','Amount (AUD)']]
    for d in details:
        rows.append([d['description'],f"{d['hours']:.2f}",f"${d['rate']:.2f}" if d['hours'] else '-',f"${d['amount']:.2f}"])
    parts += [table(rows,[70*mm,26*mm,36*mm,41*mm]),Spacer(1,14),P(f'Gross earnings: ${item.gross:,.2f}',s['Normal']),P(f'PAYG withholding: ${item.payg:,.2f}',s['Normal']),P(f'Other deductions: ${item.deduction:,.2f}',s['Normal']),P(f'NET PAY: ${item.net:,.2f}',s['Heading2']),Spacer(1,8),P(f'Super guarantee accrued (12%, qualifying earnings estimate): ${item.super_amount:,.2f}',s['Normal']),P(f'Super fund: {emp.super_fund} | Member reference: {emp.super_member}',s['MetaSmall']),Spacer(1,12),P('This document is generated from recorded timesheets. Confirm award classifications, penalties, leave, tax variations and super payment; STP reporting and SuperStream remittance are not provided.',s['MetaSmall'])]
    return document(f'Payslip {emp.employee_code}',parts)

def qr_png(value):
    image=qrcode.make(value)
    out=io.BytesIO();image.save(out,format='PNG');return out.getvalue()

def asset_label_pdf(eq,url,site_name='Warehouse'):
    s=styles();out=io.BytesIO(); doc=SimpleDocTemplate(out,pagesize=(100*mm,70*mm),leftMargin=6*mm,rightMargin=6*mm,topMargin=4*mm,bottomMargin=3*mm)
    logo=P('CRYSTAL CLEANING',s['Heading3']);title=P(eq.name[:42],s['Normal'])
    barcode=code128.Code128(eq.asset_code,barWidth=.32*mm,barHeight=12*mm,humanReadable=True)
    qr=Image(io.BytesIO(qr_png(url)),width=24*mm,height=24*mm)
    info=P(f'{eq.asset_code}  |  {site_name[:40]}',s['MetaSmall'])
    t=Table([[logo,qr],[title,qr],[info,qr],[barcode,'']],[61*mm,25*mm],rowHeights=[9*mm,8*mm,8*mm,16*mm])
    t.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('SPAN',(1,0),(1,2))]))
    doc.build([t]);return out.getvalue()
