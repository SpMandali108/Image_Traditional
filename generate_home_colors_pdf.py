"""
Generate High-Quality PDF Showcase for Image Traditional Homepage Colors
Including CMYK, RGB, and Hexadecimal Formats.
"""

import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas to dynamically compute and draw total page numbers,
    decorative header rules, and official brand footers on every page.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_decorations(self, page_count):
        self.saveState()
        page_w, page_h = A4
        
        # Running Top Header (Pages 2+)
        if self._pageNumber > 1:
            self.setStrokeColor(HexColor('#E2E8F0'))
            self.setLineWidth(0.75)
            self.line(36, page_h - 32, page_w - 36, page_h - 32)
            
            # Gold accent tick
            self.setStrokeColor(HexColor('#D4AF37'))
            self.setLineWidth(2)
            self.line(36, page_h - 32, 110, page_h - 32)
            
            self.setFont('Helvetica-Bold', 7.5)
            self.setFillColor(HexColor('#0F172A'))
            self.drawString(36, page_h - 26, "IMAGE TRADITIONAL")
            
            self.setFont('Helvetica', 7.5)
            self.setFillColor(HexColor('#64748B'))
            self.drawString(130, page_h - 26, "•  Homepage Color Specification Guide (CMYK / RGB / HEX)")
            
            self.drawRightString(page_w - 36, page_h - 26, "AHMEDABAD, GUJARAT")

        # Running Bottom Footer (All Pages)
        self.setStrokeColor(HexColor('#E2E8F0'))
        self.setLineWidth(0.75)
        self.line(36, 36, page_w - 36, 36)
        
        # Gold accent tick on footer
        self.setStrokeColor(HexColor('#D4AF37'))
        self.setLineWidth(2)
        self.line(page_w - 110, 36, page_w - 36, 36)

        self.setFont('Helvetica', 7.5)
        self.setFillColor(HexColor('#64748B'))
        self.drawString(36, 24, "Image Traditional © 2026  |  Brand Identity & UI Design System  |  Confidential & Proprietary")
        
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.setFont('Helvetica-Bold', 8)
        self.setFillColor(HexColor('#0F172A'))
        self.drawRightString(page_w - 36, 24, page_str)
        
        self.restoreState()


def hex_to_rgb(hex_code):
    hex_code = hex_code.lstrip('#')
    return tuple(int(hex_code[i:i+2], 16) for i in (0, 2, 4))


def rgb_to_cmyk(r, g, b):
    """
    Convert 0-255 sRGB coordinates into standard subtractive CMYK percentages.
    """
    if r == 0 and g == 0 and b == 0:
        return 0, 0, 0, 100
    r_n, g_n, b_n = r / 255.0, g / 255.0, b / 255.0
    k = 1.0 - max(r_n, g_n, b_n)
    if k >= 0.9999:
        return 0, 0, 0, 100
    c = (1.0 - r_n - k) / (1.0 - k)
    m = (1.0 - g_n - k) / (1.0 - k)
    y = (1.0 - b_n - k) / (1.0 - k)
    return round(c * 100), round(m * 100), round(y * 100), round(k * 100)


def build_color_table(colors_list, styles):
    """
    Constructs an elegant, readable table showcasing color swatches,
    names, descriptions, HEX, RGB, and CMYK formats.
    """
    # Usable width = 523.27 pt
    # Col widths: Swatch(54), Name/Role(142), Hex(66), RGB(88), CMYK(105), Token/Use(68)
    col_widths = [54, 142, 66, 88, 105, 68]
    
    header_data = [
        [
            Paragraph("<b>SWATCH</b>", styles['TableHeader']),
            Paragraph("<b>COLOR NAME &amp; USAGE</b>", styles['TableHeader']),
            Paragraph("<b>HEXADECIMAL</b>", styles['TableHeader']),
            Paragraph("<b>RGB (sRGB)</b>", styles['TableHeader']),
            Paragraph("<b>CMYK (PRINT)</b>", styles['TableHeader']),
            Paragraph("<b>CSS / ROLE</b>", styles['TableHeader'])
        ]
    ]
    
    table_rows = []
    table_styles = [
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#0F172A')),
        ('TEXTCOLOR', (0, 0), (-1, 0), HexColor('#FFFFFF')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, 0), 5),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#E2E8F0')),
    ]
    
    row_idx = 1
    for item in colors_list:
        name = item['name']
        hex_val = item['hex'].upper()
        desc = item['desc']
        token = item.get('token', '-')
        
        r, g, b = hex_to_rgb(hex_val)
        c, m, y, k = rgb_to_cmyk(r, g, b)
        
        rgb_str = f"rgb({r}, {g}, {b})"
        cmyk_str = f"C:{c}% M:{m}%<br/>Y:{y}% K:{k}%"
        
        # Swatch block using a nested mini-table with background color
        border_col = '#CBD5E1' if (r+g+b > 650 or r+g+b < 80) else hex_val
        swatch_cell = Table(
            [['']],
            colWidths=[42],
            rowHeights=[30],
            style=[
                ('BACKGROUND', (0, 0), (-1, -1), HexColor(hex_val)),
                ('BOX', (0, 0), (-1, -1), 1, HexColor(border_col)),
            ]
        )
        
        name_cell = Paragraph(
            f"<b><font color='#0F172A' size='8.5'>{name}</font></b><br/>"
            f"<font color='#64748B' size='7'>{desc}</font>",
            styles['TableCell']
        )
        
        hex_cell = Paragraph(
            f"<b><font color='#0F172A' size='8'>{hex_val}</font></b>",
            styles['TableCell']
        )
        
        rgb_cell = Paragraph(
            f"<font color='#1E293B' size='7.5'><b>{rgb_str}</b><br/>"
            f"<font color='#64748B' size='6.5'>R:{r} G:{g} B:{b}</font></font>",
            styles['TableCell']
        )
        
        cmyk_cell = Paragraph(
            f"<font color='#1E293B' size='7.5'><b>{cmyk_str}</b></font>",
            styles['TableCell']
        )
        
        token_cell = Paragraph(
            f"<code><font color='#0F766E' size='7'><b>{token}</b></font></code>",
            styles['TableCell']
        )
        
        table_rows.append([swatch_cell, name_cell, hex_cell, rgb_cell, cmyk_cell, token_cell])
        
        # Alternating subtle row tint
        if row_idx % 2 == 1:
            table_styles.append(('BACKGROUND', (0, row_idx), (-1, row_idx), HexColor('#F8FAFC')))
        else:
            table_styles.append(('BACKGROUND', (0, row_idx), (-1, row_idx), HexColor('#FFFFFF')))
            
        table_styles.append(('TOPPADDING', (0, row_idx), (-1, row_idx), 4))
        table_styles.append(('BOTTOMPADDING', (0, row_idx), (-1, row_idx), 4))
        row_idx += 1
        
    full_table = Table(header_data + table_rows, colWidths=col_widths, repeatRows=1)
    full_table.setStyle(TableStyle(table_styles))
    return full_table


def create_prominent_swatch_card(name, hex_val, desc, role, token, styles):
    """
    Creates a prominent horizontal swatch card for primary brand signature colors.
    """
    r, g, b = hex_to_rgb(hex_val)
    c, m, y, k = rgb_to_cmyk(r, g, b)
    
    luminance = (0.299 * r + 0.587 * g + 0.114 * b)
    text_color = '#000000' if luminance > 140 else '#FFFFFF'
    border_color = '#D1D5DB' if luminance > 220 else hex_val
    
    swatch_box = Table(
        [[Paragraph(f"<font color='{text_color}' size='9'><b>{hex_val}</b></font>", styles['CenterText'])]],
        colWidths=[76],
        rowHeights=[50],
        style=[
            ('BACKGROUND', (0, 0), (-1, -1), HexColor(hex_val)),
            ('BOX', (0, 0), (-1, -1), 1, HexColor(border_color)),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]
    )
    
    info_html = (
        f"<b><font color='#0F172A' size='9.5'>{name}</font></b> "
        f"<font color='#B45309' size='8'>[{role}]</font><br/>"
        f"<font color='#475569' size='7.5'>{desc}</font><br/>"
        f"<font color='#0F172A' size='7.5'>"
        f"<b>HEX:</b> {hex_val} &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"<b>RGB:</b> ({r}, {g}, {b}) &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"<b>CMYK:</b> C:{c}% M:{m}% Y:{y}% K:{k}% &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"<b>Token:</b> <code>{token}</code>"
        f"</font>"
    )
    info_cell = Paragraph(info_html, styles['Normal'])
    
    card_table = Table(
        [[swatch_box, info_cell]],
        colWidths=[84, 439],
        style=[
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, 0), (-1, -1), HexColor('#FFFFFF')),
            ('BOX', (0, 0), (-1, -1), 0.75, HexColor('#E2E8F0')),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]
    )
    return card_table


def generate_pdf(output_path):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=38,
        bottomMargin=42
    )
    
    styles = getSampleStyleSheet()
    
    # Custom Typography Styles
    styles.add(ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=HexColor('#0F172A')
    ))
    
    styles.add(ParagraphStyle(
        'SectionHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11.5,
        leading=15,
        textColor=HexColor('#0F172A'),
        spaceBefore=8,
        spaceAfter=3
    ))
    
    styles.add(ParagraphStyle(
        'SectionSub',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.8,
        leading=10.5,
        textColor=HexColor('#475569'),
        spaceAfter=5
    ))
    
    styles.add(ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=9,
        textColor=HexColor('#FFFFFF'),
        alignment=0
    ))
    
    styles.add(ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=10,
        textColor=HexColor('#1E293B')
    ))
    
    styles.add(ParagraphStyle(
        'CenterText',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        alignment=1
    ))
    
    styles.add(ParagraphStyle(
        'MetaVal',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=10,
        textColor=HexColor('#334155')
    ))
    
    styles.add(ParagraphStyle(
        'CalloutText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=11,
        textColor=HexColor('#1E293B')
    ))
    
    story = []
    
    # ── Header Banner with Logo & Titles (Page 1) ──
    logo_path = 'website/static/Home_Img/favicon.png'
    logo_img = None
    if os.path.exists(logo_path):
        logo_img = Image(logo_path, width=52, height=52)
        
    title_text = (
        "<b><font size='17' color='#0F172A'>IMAGE TRADITIONAL</font></b><br/>"
        "<b><font size='11.5' color='#D4AF37'>HOMEPAGE COLOR PALETTE &amp; BRAND STYLE GUIDE</font></b><br/>"
        "<font size='7.5' color='#475569'>Comprehensive Color Specifications: CMYK (Print), RGB (Digital Displays) &amp; Hexadecimal (Web UI)</font>"
    )
    title_p = Paragraph(title_text, styles['Normal'])
    
    header_table = Table(
        [[logo_img, title_p] if logo_img else [title_p]],
        colWidths=[60, 463] if logo_img else [523],
        style=[
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]
    )
    story.append(header_table)
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=1.5, color=HexColor('#D4AF37'), spaceAfter=6))
    
    # ── Metadata Box ──
    meta_content = [
        [
            Paragraph("<b>Project:</b> Image Traditional Rental Web App", styles['MetaVal']),
            Paragraph("<b>Scope:</b> Homepage, Nav, Hero &amp; Festive Cards", styles['MetaVal']),
            Paragraph("<b>Location:</b> Ahmedabad, Gujarat, India", styles['MetaVal']),
        ],
        [
            Paragraph("<b>Digital Standard:</b> sRGB IEC61966-2.1", styles['MetaVal']),
            Paragraph("<b>Print Standard:</b> Coated FOGRA39 / SWOP v2", styles['MetaVal']),
            Paragraph("<b>Date:</b> September 2026 (Active Cycle)", styles['MetaVal']),
        ]
    ]
    meta_table = Table(meta_content, colWidths=[174, 184, 165], style=[
        ('BACKGROUND', (0, 0), (-1, -1), HexColor('#F8FAFC')),
        ('BOX', (0, 0), (-1, -1), 0.75, HexColor('#E2E8F0')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 7),
        ('RIGHTPADDING', (0, 0), (-1, -1), 7),
    ])
    story.append(meta_table)
    story.append(Spacer(1, 6))
    
    # Overview Note
    intro_p = Paragraph(
        "<b>Executive Overview:</b> This specification guide establishes the authoritative color system for the <b>Image Traditional</b> "
        "homepage. The visual identity harmonizes authentic Gujarati festive traditions—specifically Navratri Garba celebrations, "
        "regal royal Rajputana brocade, warm terracotta earthen diyas, and sacred mango leaf Toran garlands. Every hue is defined with exact "
        "<b>Hexadecimal (#RRGGBB)</b> for web development, <b>sRGB</b> coordinates for digital screens, and subtractive <b>CMYK</b> percentages "
        "for commercial offset printing, brochures, catalogs, and outdoor flex banners.",
        styles['CalloutText']
    )
    story.append(intro_p)
    story.append(Spacer(1, 8))
    
    # ── Section 1: Core Brand & Royal Metallics ──
    story.append(Paragraph("1. Primary Brand &amp; Royal Metallic Palette", styles['SectionHeader']))
    story.append(Paragraph(
        "The golden and metallic hues anchor the festive aura of Image Traditional, delivering warmth, divinity, and cultural luxury.",
        styles['SectionSub']
    ))
    
    card1 = create_prominent_swatch_card(
        name="Swarna Gold (Traditional Festive Gold)",
        hex_val="#D4AF37",
        desc="Primary brand accent. Applied to the emblem logo, hero glowing mandalas, Toran garlands, bead accents, and decorative divider gems.",
        role="Primary Brand Accent",
        token="--theme-gold / --gold",
        styles=styles
    )
    card2 = create_prominent_swatch_card(
        name="Antique Deep Gold (Heritage Swarna)",
        hex_val="#B8961E",
        desc="Deep metallic shadow tone. Applied to secondary garland lines, earthen diya clay gradients, active button borders, and junction nodes.",
        role="Secondary Metallic Shadow",
        token="--theme-gold-dark / --gold-dark",
        styles=styles
    )
    story.append(card1)
    story.append(Spacer(1, 4))
    story.append(card2)
    story.append(Spacer(1, 6))
    
    primary_metallics_table_data = [
        {
            'name': 'Marigold Kesari Gold',
            'hex': '#F59E0B',
            'desc': 'High-energy CTA buttons ("Explore Collections", "Book Now"), glowing status dots',
            'token': 'CTA Primary'
        },
        {
            'name': 'Champagne Soft Gold',
            'hex': '#F5D580',
            'desc': 'Button hover gradients, modal title illumination, radial light glints',
            'token': 'Glow Highlight'
        },
        {
            'name': 'Warm Light Ivory',
            'hex': '#FFF7CE',
            'desc': 'Center beam of hero typographic gradient ("Image Traditional" title), spark overlays',
            'token': 'Radial Shimmer'
        },
        {
            'name': 'Warm Sand Amber',
            'hex': '#FCD34D',
            'desc': 'Chaniya Choli eyebrow category tag, banner subtitle accents',
            'token': 'Tag Accent'
        }
    ]
    story.append(build_color_table(primary_metallics_table_data, styles))
    story.append(Spacer(1, 8))
    
    # Color Models Explanatory Box at bottom of Page 1
    models_box_data = [
        [
            Paragraph("<b>COLOR FORMAT REPRODUCTION FUNDAMENTALS</b>", styles['TableHeader']),
        ],
        [
            Paragraph(
                "• <b>Hexadecimal (#RRGGBB):</b> 6-digit base-16 code specifying byte values (00-FF) for Red, Green, and Blue channels. Standard for CSS3 styling and HTML web presentation.<br/>"
                "• <b>RGB (sRGB Color Space):</b> Additive color model for self-illuminating display hardware (OLED, IPS, Retina screens). Expressed in integer coordinates (0-255).<br/>"
                "• <b>CMYK (Process Color):</b> Subtractive ink model (Cyan, Magenta, Yellow, Key/Black) calibrated for 4-color commercial offset printing, hoardings, and garment tags.",
                styles['TableCell']
            )
        ]
    ]
    models_table = Table(models_box_data, colWidths=[523], style=[
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#0F172A')),
        ('BACKGROUND', (0, 1), (-1, 1), HexColor('#F8FAFC')),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#CBD5E1')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ])
    story.append(models_table)
    
    # End of Page 1 -> Page Break
    story.append(PageBreak())
    
    # ── Section 2: Canvas, Surface & Structural Base (Page 2) ──
    story.append(Paragraph("2. Canvas, Surface &amp; Structural Architecture", styles['SectionHeader']))
    story.append(Paragraph(
        "The dual foundation provides both an immersive dark glassmorphic night theme and an authentic warm festive ivory canvas.",
        styles['SectionSub']
    ))
    
    canvas_table_data = [
        {
            'name': 'Midnight Navy Base',
            'hex': '#0A1929',
            'desc': 'Deepest theme base, footer background, costume circular glass inner background',
            'token': '--theme-navy / --navy'
        },
        {
            'name': 'Slate Night Canvas',
            'hex': '#0F172A',
            'desc': 'Primary dark mode background canvas, outer hero gradient, toast banners',
            'token': '--theme-bg / --bg'
        },
        {
            'name': 'Charcoal Slate Surface',
            'hex': '#1E293B',
            'desc': 'Main header navigation background, category card backgrounds, contact menu',
            'token': '--theme-surface'
        },
        {
            'name': 'Subtle Slate Border',
            'hex': '#334155',
            'desc': 'Header bottom border line, card structural dividers, earthen diya stroke',
            'token': '--theme-border'
        },
        {
            'name': 'Festive Warm Cream / Ivory',
            'hex': '#FFFDF7',
            'desc': 'Light mode reference canvas, "Tradition Wears Happiness" promotional banner background',
            'token': 'Light Canvas Base'
        },
        {
            'name': 'Mandala Watermark Sand',
            'hex': '#F3E8D2',
            'desc': 'Delicate background filigree rangolis, traditional floral mandalas in light hero section',
            'token': 'Ornamental Watermark'
        }
    ]
    story.append(build_color_table(canvas_table_data, styles))
    story.append(Spacer(1, 14))
    
    # ── Section 3: Signature Festive Category Cards ──
    story.append(Paragraph("3. Signature Festive Category Card Colors", styles['SectionHeader']))
    story.append(Paragraph(
        "Each costume category features an authentic, culturally evocative identity color calibrated for rich visual depth.",
        styles['SectionSub']
    ))
    
    category_cards_data = [
        {
            'name': 'Regal Burgundy Maroon',
            'hex': '#4A0E17',
            'desc': '"Fancy Dresses" card background: evokes royal court attire, historical & mythological drama costumes',
            'token': 'Card Fancy Dress'
        },
        {
            'name': 'Fancy Rose Highlight',
            'hex': '#F472B6',
            'desc': '"Fancy Dresses" card eyebrow tag text, secondary card bead highlights',
            'token': 'Tag / Eyebrow'
        },
        {
            'name': 'Royal Midnight Indigo',
            'hex': '#1E123F',
            'desc': '"Traditional Kediya" card background: evokes nocturnal Gujarat Navratri Garba celebrations under the night sky',
            'token': 'Card Kediya'
        },
        {
            'name': 'Kediya Lavender Highlight',
            'hex': '#C084FC',
            'desc': '"Traditional Kediya" card eyebrow tag text, male dancer aura glow',
            'token': 'Tag / Eyebrow'
        },
        {
            'name': 'Espresso Bronze Ochre',
            'hex': '#332211',
            'desc': '"Chaniya Choli" card background: represents traditional Gujarati terracotta clay and warm mirror-work embroidery',
            'token': 'Card Choli'
        },
        {
            'name': 'Choli Warm Sand Highlight',
            'hex': '#FCD34D',
            'desc': '"Chaniya Choli" card eyebrow tag text, embroidered mirror bead flare',
            'token': 'Tag / Eyebrow'
        }
    ]
    story.append(build_color_table(category_cards_data, styles))
    
    # End of Page 2 -> Page Break
    story.append(PageBreak())
    
    # ── Section 4: Cultural & Festive Accents (Page 3) ──
    story.append(Paragraph("4. Cultural Folk Accents, Garba Silks &amp; Auspicious Flora", styles['SectionHeader']))
    story.append(Paragraph(
        "Vibrant Gujarati folk tones derived from traditional textiles, auspicious mango leaves, and festive dandiya sticks.",
        styles['SectionSub']
    ))
    
    cultural_table_data = [
        {
            'name': 'Garba Rani Pink',
            'hex': '#DC2743',
            'desc': 'Flared Garba choli skirt silk, luxury Instagram redirect button gradient center, festive celebration',
            'token': 'Festive Silk Pink'
        },
        {
            'name': 'Dandiya Vermilion Red',
            'hex': '#DC2626',
            'desc': 'Male dancer traditional Kediya jacket, sacred dandiya wooden sticks, attention markers',
            'token': 'Sindoor Red'
        },
        {
            'name': 'Celestial Shiva Cyan',
            'hex': '#38BDF8',
            'desc': 'Lord Shiva mythological fancy dress illustration, divine aura, sky and trishul reflections',
            'token': 'Mythological Cyan'
        },
        {
            'name': 'Sacred Mango Leaf Green',
            'hex': '#15803D',
            'desc': 'Hanging Toran garland mango leaves (sacred Indian symbol of good fortune and warm welcome)',
            'token': 'Toran Foliage Deep'
        },
        {
            'name': 'Auspicious Leaf Emerald',
            'hex': '#16A34A',
            'desc': 'Secondary leaf gradient in Toran garland, fresh festive greenery and nature accents',
            'token': 'Toran Leaf Vibrant'
        },
        {
            'name': 'Sunset Tangerine Orange',
            'hex': '#F09433',
            'desc': 'Instagram luxury button gradient start, marigold flower petal variation',
            'token': 'Marigold Orange'
        },
        {
            'name': 'Royal Silk Violet',
            'hex': '#BC1888',
            'desc': 'Instagram luxury button gradient terminal, traditional Gujarati patola silk border accent',
            'token': 'Patola Violet'
        }
    ]
    story.append(build_color_table(cultural_table_data, styles))
    story.append(Spacer(1, 14))
    
    # ── Section 5: Typographic & Neutral UI System ──
    story.append(Paragraph("5. Typographic, Neutral UI &amp; Contrast System", styles['SectionHeader']))
    story.append(Paragraph(
        "Neutrals and text tones engineered for WCAG AA compliance and effortless readability across both dark and light surfaces.",
        styles['SectionSub']
    ))
    
    neutrals_table_data = [
        {
            'name': 'Silk White Text',
            'hex': '#F1F5F9',
            'desc': 'Primary high-contrast readable text and headings on dark surfaces (Slate 100)',
            'token': '--theme-text / --text'
        },
        {
            'name': 'Mirror Bead Silver',
            'hex': '#CBD5E1',
            'desc': 'Hand-crafted traditional mirror beads border surrounding circular category frames (Slate 300)',
            'token': 'Mirror Bead Shimmer'
        },
        {
            'name': 'Muted Slate Typography',
            'hex': '#94A3B8',
            'desc': 'Secondary subtitles, descriptive paragraphs, footer copyright notices (Slate 400)',
            'token': '--theme-muted / --muted'
        },
        {
            'name': 'Dominant Headline Charcoal',
            'hex': '#111827',
            'desc': 'Primary headline typography in light canvas mode ("Celebrate Navratri With Tradition")',
            'token': 'Light Mode Title'
        },
        {
            'name': 'Body Slate Charcoal',
            'hex': '#475569',
            'desc': 'Secondary body copy in light canvas mode, rental process descriptions (Slate 600)',
            'token': 'Light Mode Body'
        },
        {
            'name': 'Pure Crisp White',
            'hex': '#FFFFFF',
            'desc': 'High-key sparkle glints, white badge backgrounds, "View Catalogue" button interior',
            'token': 'White / Pure Light'
        }
    ]
    story.append(build_color_table(neutrals_table_data, styles))
    
    # End of Page 3 -> Page Break
    story.append(PageBreak())
    
    # ── Section 6: Homepage Visual Architecture & Color Mapping (Page 4) ──
    story.append(Paragraph("6. Homepage Visual Architecture &amp; Color Mapping", styles['SectionHeader']))
    story.append(Paragraph(
        "Visual breakdown mapping each homepage interface zone directly to its designated color palette specifications.",
        styles['SectionSub']
    ))
    
    ref_image_path = 'design-reference/home-reference.png'
    ref_img = None
    if os.path.exists(ref_image_path):
        ref_img = Image(ref_image_path, width=205, height=236)
        
    mapping_text = (
        "<b>HOMEPAGE ZONE COLOR ALLOCATIONS:</b><br/><br/>"
        "<b>1. Navigation Bar:</b><br/>"
        "• Header Background: <b>#FFFFFF</b> (Pure White) with <b>#D4AF37</b> gold bottom border<br/>"
        "• Logo Emblem: Multi-color traditional Gujarati mandala medallion<br/>"
        "• Primary Action: <b>#D4AF37</b> Gold border with dark text<br/><br/>"
        "<b>2. Hero Banner:</b><br/>"
        "• Canvas: <b>#FFFDF7</b> (Warm Festive Cream) with <b>#F3E8D2</b> watermark mandalas<br/>"
        "• Title Headline: <b>#111827</b> (Deep Charcoal) with <b>#D4AF37 / #F59E0B</b> (Swarna Gold)<br/>"
        "• Primary CTA: <b>#F59E0B</b> (Marigold Amber) pill button with arrow<br/>"
        "• Secondary CTA: <b>#FFFFFF</b> pill with <b>#334155</b> border<br/><br/>"
        "<b>3. Metric Badges:</b><br/>"
        "• Icon Accents: <b>#F59E0B</b> (Amber Gold) customer &amp; trust badges<br/><br/>"
        "<b>4. Category Showcase Cards:</b><br/>"
        "• Fancy Dresses: <b>#4A0E17</b> (Regal Burgundy) with <b>#F472B6</b> tag<br/>"
        "• Traditional Kediya: <b>#1E123F</b> (Midnight Indigo) with <b>#C084FC</b> tag<br/>"
        "• Chaniya Choli: <b>#332211</b> (Espresso Bronze) with <b>#FCD34D</b> tag<br/>"
        "• Mirror Frame: <b>#CBD5E1</b> (Silver mirror beads border)<br/><br/>"
        "<b>5. Promotional Banner:</b><br/>"
        "• Background: <b>#FFFDF7</b> with sacred dandiya sticks in <b>#DC2626</b><br/>"
        "• CTA Button: <b>#F59E0B</b> (Warm Saffron Gold)<br/><br/>"
        "<b>6. Midnight Footer:</b><br/>"
        "• Background: <b>#0A1929</b> (Deep Midnight Navy)<br/>"
        "• Text &amp; Accents: <b>#94A3B8</b> (Muted Slate) &amp; <b>#F1F5F9</b> (Silk White)"
    )
    mapping_p = Paragraph(mapping_text, styles['CalloutText'])
    
    zone_table = Table(
        [[ref_img, mapping_p] if ref_img else [mapping_p]],
        colWidths=[215, 308] if ref_img else [523],
        style=[
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BACKGROUND', (0, 0), (-1, -1), HexColor('#F8FAFC')),
            ('BOX', (0, 0), (-1, -1), 0.75, HexColor('#E2E8F0')),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]
    )
    story.append(zone_table)
    story.append(Spacer(1, 14))
    
    # ── Section 7: Print Production & Color Reproduction Standards ──
    story.append(Paragraph("7. Commercial Print &amp; Digital Reproduction Standards", styles['SectionHeader']))
    story.append(Paragraph(
        "Critical technical guidelines for graphic designers, commercial printers, and flex banner manufacturers.",
        styles['SectionSub']
    ))
    
    print_guide_data = [
        [
            Paragraph("<b>OUTPUT MEDIUM</b>", styles['TableHeader']),
            Paragraph("<b>COLOR PROFILE &amp; SPACE</b>", styles['TableHeader']),
            Paragraph("<b>SUBSTRATE &amp; PAPER STOCK</b>", styles['TableHeader']),
            Paragraph("<b>SPECIAL FINISHING RECOMMENDATIONS</b>", styles['TableHeader']),
        ],
        [
            Paragraph("<b>Web &amp; Mobile UI</b>", styles['TableCell']),
            Paragraph("sRGB IEC61966-2.1<br/>8-bit per channel", styles['TableCell']),
            Paragraph("OLED / IPS Display screens<br/>72 - 450 PPI density", styles['TableCell']),
            Paragraph("Hardware-accelerated CSS filters, radial glow overlays, glassmorphic backdrop-blur.", styles['TableCell']),
        ],
        [
            Paragraph("<b>Commercial Print (Brochures &amp; Catalogs)</b>", styles['TableCell']),
            Paragraph("CMYK Coated FOGRA39<br/>ISO 12647-2 Standard", styles['TableCell']),
            Paragraph("170 - 300 GSM Art Paper /<br/>Velvet Matte Finish", styles['TableCell']),
            Paragraph("Spot UV on circular mirror frames. Gold hot-foil stamping for #D4AF37 Swarna Gold logo &amp; mandalas.", styles['TableCell']),
        ],
        [
            Paragraph("<b>Outdoor Banners &amp; Event Hoardings</b>", styles['TableCell']),
            Paragraph("CMYK US Web Coated (SWOP) v2<br/>Rich Black: C:60 M:40 Y:40 K:100", styles['TableCell']),
            Paragraph("Heavyweight Star Flex /<br/>Backlit Vinyl Fabric", styles['TableCell']),
            Paragraph("High UV-resistant solvent inks to preserve vibrant reds (#DC2626) and rani pink (#DC2743) against Gujarat sunlight.", styles['TableCell']),
        ],
        [
            Paragraph("<b>Garment Hangtags &amp; Packaging</b>", styles['TableCell']),
            Paragraph("Pantone + CMYK Process<br/>Pantone 871 C (Gold Metallic)", styles['TableCell']),
            Paragraph("350 GSM Ivory Kraft Card /<br/>Recycled Textured Board", styles['TableCell']),
            Paragraph("Embossed mandala filigree with metallic gold foil stamping on deep midnight navy (#0A1929) board.", styles['TableCell']),
        ],
    ]
    print_table = Table(print_guide_data, colWidths=[105, 125, 133, 160], style=[
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#0F172A')),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#CBD5E1')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('BACKGROUND', (0, 1), (-1, 1), HexColor('#FFFFFF')),
        ('BACKGROUND', (0, 2), (-1, 2), HexColor('#F8FAFC')),
        ('BACKGROUND', (0, 3), (-1, 3), HexColor('#FFFFFF')),
        ('BACKGROUND', (0, 4), (-1, 4), HexColor('#F8FAFC')),
    ])
    story.append(print_table)
    
    # End of Page 4 -> Page Break
    story.append(PageBreak())
    
    # ── Section 8: Quick-Glance Color Spectrum Ribbon (Page 5) ──
    story.append(Paragraph("8. Master Color Spectrum Ribbon &amp; Developer CSS Export", styles['SectionHeader']))
    story.append(Paragraph(
        "Complete visual spectrum of all 24 curated brand colors alongside copy-pasteable CSS variable declarations.",
        styles['SectionSub']
    ))
    
    # Visual Ribbon of 24 Swatches (2 rows of 12)
    ribbon_colors_row1 = [
        ('#D4AF37', 'Swarna'), ('#B8961E', 'Antique'), ('#F59E0B', 'Marigold'), ('#F5D580', 'Champagne'),
        ('#FFF7CE', 'Ivory'), ('#FCD34D', 'Sand'), ('#0A1929', 'Navy'), ('#0F172A', 'Slate 900'),
        ('#1E293B', 'Slate 800'), ('#334155', 'Slate 700'), ('#FFFDF7', 'Cream'), ('#F3E8D2', 'Watermark')
    ]
    ribbon_colors_row2 = [
        ('#4A0E17', 'Burgundy'), ('#F472B6', 'Rose'), ('#1E123F', 'Indigo'), ('#C084FC', 'Lavender'),
        ('#332211', 'Ochre'), ('#DC2743', 'Rani Pink'), ('#DC2626', 'Vermilion'), ('#38BDF8', 'Cyan'),
        ('#15803D', 'Mango'), ('#16A34A', 'Emerald'), ('#F1F5F9', 'Silk White'), ('#111827', 'Charcoal')
    ]
    
    def build_ribbon_row(swatches):
        row_cells = []
        cell_styles = []
        col_w = 523 / len(swatches)
        for idx, (hx, lbl) in enumerate(swatches):
            r, g, b = hex_to_rgb(hx)
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            txt_col = '#000000' if lum > 140 else '#FFFFFF'
            border_col = '#CBD5E1' if (lum > 220 or lum < 20) else hx
            
            p = Paragraph(f"<font color='{txt_col}' size='5.5'><b>{lbl}</b><br/>{hx}</font>", styles['CenterText'])
            row_cells.append(p)
            cell_styles.extend([
                ('BACKGROUND', (idx, 0), (idx, 0), HexColor(hx)),
                ('BOX', (idx, 0), (idx, 0), 0.75, HexColor(border_col)),
                ('VALIGN', (idx, 0), (idx, 0), 'MIDDLE'),
                ('ALIGN', (idx, 0), (idx, 0), 'CENTER'),
                ('TOPPADDING', (idx, 0), (idx, 0), 4),
                ('BOTTOMPADDING', (idx, 0), (idx, 0), 4),
                ('LEFTPADDING', (idx, 0), (idx, 0), 1),
                ('RIGHTPADDING', (idx, 0), (idx, 0), 1),
            ])
        t = Table([row_cells], colWidths=[col_w]*len(swatches), rowHeights=[26])
        t.setStyle(TableStyle(cell_styles))
        return t
        
    story.append(build_ribbon_row(ribbon_colors_row1))
    story.append(Spacer(1, 2))
    story.append(build_ribbon_row(ribbon_colors_row2))
    story.append(Spacer(1, 8))
    
    css_code = (
        "/* ── Image Traditional Authoritative Color System (sRGB / HEX / CMYK) ── */<br/>"
        ":root {<br/>"
        "&nbsp;&nbsp;/* Core Brand Metallics */<br/>"
        "&nbsp;&nbsp;--theme-gold:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#D4AF37; /* Swarna Gold: rgb(212, 175, 55) | CMYK: 0%, 17%, 74%, 17% */<br/>"
        "&nbsp;&nbsp;--theme-gold-dark:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#B8961E; /* Antique Gold: rgb(184, 150, 30) | CMYK: 0%, 18%, 84%, 28% */<br/>"
        "&nbsp;&nbsp;--theme-kesari:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#F59E0B; /* Marigold CTA: rgb(245, 158, 11) | CMYK: 0%, 36%, 96%, 4% */<br/>"
        "&nbsp;&nbsp;--theme-gold-light:&nbsp;&nbsp;&nbsp;&nbsp;#F5D580; /* Champagne Shimmer: rgb(245, 213, 128) | CMYK: 0%, 13%, 48%, 4% */<br/>"
        "<br/>"
        "&nbsp;&nbsp;/* Canvas &amp; Surfaces */<br/>"
        "&nbsp;&nbsp;--theme-navy:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#0A1929; /* Midnight Navy: rgb(10, 25, 41) | CMYK: 76%, 39%, 0%, 84% */<br/>"
        "&nbsp;&nbsp;--theme-bg:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#0F172A; /* Slate Night: rgb(15, 23, 42) | CMYK: 64%, 45%, 0%, 84% */<br/>"
        "&nbsp;&nbsp;--theme-surface:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#1E293B; /* Slate Surface: rgb(30, 41, 59) | CMYK: 49%, 31%, 0%, 77% */<br/>"
        "&nbsp;&nbsp;--theme-border:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#334155; /* Slate Border: rgb(51, 65, 85) | CMYK: 40%, 24%, 0%, 67% */<br/>"
        "&nbsp;&nbsp;--theme-cream:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#FFFDF7; /* Warm Festive Cream: rgb(255, 253, 247) | CMYK: 0%, 1%, 3%, 0% */<br/>"
        "<br/>"
        "&nbsp;&nbsp;/* Category Cards */<br/>"
        "&nbsp;&nbsp;--card-fancy:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#4A0E17; /* Regal Burgundy: rgb(74, 14, 23) | CMYK: 0%, 81%, 69%, 71% */<br/>"
        "&nbsp;&nbsp;--card-kediya:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#1E123F; /* Midnight Indigo: rgb(30, 18, 63) | CMYK: 52%, 71%, 0%, 75% */<br/>"
        "&nbsp;&nbsp;--card-choli:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#332211; /* Espresso Bronze: rgb(51, 34, 17) | CMYK: 0%, 33%, 67%, 80% */<br/>"
        "<br/>"
        "&nbsp;&nbsp;/* Cultural Accents &amp; Silks */<br/>"
        "&nbsp;&nbsp;--festive-rani-pink:&nbsp;&nbsp;&nbsp;#DC2743; /* Garba Rani Pink: rgb(220, 39, 67) | CMYK: 0%, 82%, 70%, 14% */<br/>"
        "&nbsp;&nbsp;--festive-vermilion:&nbsp;&nbsp;&nbsp;#DC2626; /* Dandiya Vermilion: rgb(220, 38, 38) | CMYK: 0%, 83%, 83%, 14% */<br/>"
        "&nbsp;&nbsp;--festive-shiva-cyan:&nbsp;&nbsp;#38BDF8; /* Celestial Sky: rgb(56, 189, 248) | CMYK: 77%, 24%, 0%, 3% */<br/>"
        "&nbsp;&nbsp;--toran-leaf-deep:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#15803D; /* Sacred Mango Leaf: rgb(21, 128, 61) | CMYK: 84%, 0%, 52%, 50% */<br/>"
        "&nbsp;&nbsp;--toran-leaf-vibrant:&nbsp;&nbsp;#16A34A; /* Auspicious Emerald: rgb(22, 163, 74) | CMYK: 87%, 0%, 55%, 36% */<br/>"
        "<br/>"
        "&nbsp;&nbsp;/* Typography &amp; Neutrals */<br/>"
        "&nbsp;&nbsp;--theme-text:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#F1F5F9; /* Silk White Text: rgb(241, 245, 249) | CMYK: 3%, 2%, 0%, 2% */<br/>"
        "&nbsp;&nbsp;--theme-muted:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#94A3B8; /* Muted Slate: rgb(148, 163, 184) | CMYK: 20%, 11%, 0%, 28% */<br/>"
        "&nbsp;&nbsp;--mirror-bead-silver:&nbsp;&nbsp;#CBD5E1; /* Mirror Shimmer: rgb(203, 213, 225) | CMYK: 10%, 5%, 0%, 12% */<br/>"
        "&nbsp;&nbsp;--headline-charcoal:&nbsp;&nbsp;&nbsp;#111827; /* Dark Headline: rgb(17, 24, 39) | CMYK: 56%, 38%, 0%, 85% */<br/>"
        "}"
    )
    
    code_p = Paragraph(f"<font color='#0F172A' size='6.5' face='Courier'>{css_code}</font>", styles['Normal'])
    code_box = Table(
        [[code_p]],
        colWidths=[523],
        style=[
            ('BACKGROUND', (0, 0), (-1, -1), HexColor('#F1F5F9')),
            ('BOX', (0, 0), (-1, -1), 1, HexColor('#CBD5E1')),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ]
    )
    story.append(code_box)
    story.append(Spacer(1, 10))
    
    # Sign-off & Verification Block
    sign_off_data = [
        [
            Paragraph("<b>DESIGN SYSTEM APPROVAL &amp; COMPLIANCE</b>", styles['TableHeader']),
            Paragraph("<b>PRINT REPRODUCTION SIGN-OFF</b>", styles['TableHeader']),
        ],
        [
            Paragraph(
                "<b>Status:</b> Official Production Color Standard<br/>"
                "<b>Conformance:</b> WCAG 2.1 AA Compliant on respective backgrounds<br/>"
                "<b>Approved for:</b> Flask Web App, React/PWA, Digital Marketing",
                styles['TableCell']
            ),
            Paragraph(
                "<b>Commercial Inks:</b> 4-Color Process CMYK + Pantone Spot Inks<br/>"
                "<b>Foil Stamping:</b> Gold Metallic Foil for Swarna Gold (#D4AF37)<br/>"
                "<b>Vendor Handoff:</b> Ready for offset, digital &amp; outdoor production",
                styles['TableCell']
            )
        ]
    ]
    sign_off_table = Table(sign_off_data, colWidths=[261, 262], style=[
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#0F172A')),
        ('BACKGROUND', (0, 1), (-1, 1), HexColor('#FFFFFF')),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#CBD5E1')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ])
    story.append(sign_off_table)
    
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"PDF successfully generated at: {output_path}")

if __name__ == '__main__':
    out_file = 'Image_Traditional_Homepage_Color_Palette.pdf'
    generate_pdf(out_file)
