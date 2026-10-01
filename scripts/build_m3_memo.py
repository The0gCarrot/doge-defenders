"""Build the M3 memo from the notebook's measured results and saved figures."""

from pathlib import Path

from docx import Document
from docx.enum.text import WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "docs" / "m3_figures"
OUTS = [
    ROOT / "docs" / "BUA3336_M3_Doge_Defenders.docx",
    Path(r"c:\Users\gabri\Downloads\BUA3336_M3_Doge_Defenders.docx"),
]

NAVY = RGBColor(0x1F, 0x4E, 0x79)
BLACK = RGBColor(0x22, 0x22, 0x22)


def set_run(run, size=10.5, bold=False, italic=False, color=BLACK):
    run.font.name = "Calibri"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic
    run.font.color.rgb = color


def add_text(paragraph, text, size=10.5, bold=False, italic=False, color=BLACK):
    run = paragraph.add_run(text)
    set_run(run, size, bold, italic, color)
    return run


def p(doc, text="", size=10, bold=False, italic=False, space_before=1, space_after=1):
    paragraph = doc.add_paragraph()
    paragraph.paragraph_format.space_before = Pt(space_before)
    paragraph.paragraph_format.space_after = Pt(space_after)
    paragraph.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
    if text:
        add_text(paragraph, text, size, bold, italic)
    return paragraph


def heading(doc, text):
    return p(doc, text, size=11, bold=True, space_before=4, space_after=1)


def caption(doc, text):
    return p(doc, text, size=9, italic=True, space_before=1, space_after=4)


def shade(cell, hex_color):
    tc = cell._tePr if hasattr(cell, "_tePr") else cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = tcPr.makeelement(qn("w:shd"), {
        qn("w:val"): "clear",
        qn("w:color"): "auto",
        qn("w:fill"): hex_color,
    })
    tcPr.append(shd)


def table(doc, headers, rows):
    grid = doc.add_table(rows=1 + len(rows), cols=len(headers))
    grid.style = "Table Grid"
    for i, header in enumerate(headers):
        cell = grid.rows[0].cells[i]
        cell.text = ""
        paragraph = cell.paragraphs[0]
        paragraph.paragraph_format.space_before = Pt(0)
        paragraph.paragraph_format.space_after = Pt(0)
        add_text(paragraph, header, size=8, bold=True, color=RGBColor(0xFF, 0xFF, 0xFF))
        shade(cell, "1F4E79")
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            cell = grid.rows[r + 1].cells[c]
            cell.text = ""
            paragraph = cell.paragraphs[0]
            paragraph.paragraph_format.space_before = Pt(0)
            paragraph.paragraph_format.space_after = Pt(0)
            add_text(paragraph, value, size=8)
            if r % 2 == 1:
                shade(cell, "F4F7FB")
    return grid


def picture(doc, name, width):
    doc.add_picture(str(FIG / name), width=Inches(width))
    doc.paragraphs[-1].paragraph_format.space_before = Pt(1)
    doc.paragraphs[-1].paragraph_format.space_after = Pt(0)


def picture_pair(doc, left, right, width=3.35):
    grid = doc.add_table(rows=1, cols=2)
    for cell, name in zip(grid.rows[0].cells, (left, right)):
        cell.text = ""
        paragraph = cell.paragraphs[0]
        paragraph.paragraph_format.space_before = Pt(0)
        paragraph.paragraph_format.space_after = Pt(0)
        run = paragraph.add_run()
        run.add_picture(str(FIG / name), width=Inches(width))
        tc = cell._tc
        tcPr = tc.get_or_add_tcPr()
        borders = OxmlElement("w:tcBorders")
        for edge in ("top", "left", "bottom", "right"):
            element = OxmlElement(f"w:{edge}")
            element.set(qn("w:val"), "nil")
            borders.append(element)
        tcPr.append(borders)


def main():
    doc = Document()
    section = doc.sections[0]
    section.top_margin = Inches(0.5)
    section.bottom_margin = Inches(0.45)
    section.left_margin = Inches(0.6)
    section.right_margin = Inches(0.6)
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)

    p(doc, "BUA 3336 · Big Data & Data Mining for Business", size=11, bold=True, space_before=0)
    p(doc, "M3 — Exploratory Analysis Report", size=14, bold=True, space_before=0, space_after=2)
    p(doc, "Team: Doge Defenders.  Data Steward: Daniel Burke.  Modeling Lead: Gabriel McLaughlin.  AI Auditor: Augusta Domingo.  Business Translator: Mason Ocampo.  QA Lead: no separate named seat; the four members review one another's checks.")
    p(doc, "Author of this memo: Gabriel McLaughlin.  Date: October 1, 2026.")
    p(doc, "Rows in the file this memo analyzes: 525. Every comparison with the 90-day result uses the 510 rows where that result is already known.")

    heading(doc, "Part 0 — Revised target")
    p(doc, "We are predicting whether the coin's price is higher about 90 days later, for each daily report (one coin on one UTC day), using only information available at midnight UTC on that report date.")
    p(doc, "Cutoff rule, and when we chose it. The result is up (1) when the price about 90 days later is higher than the price on the report date. Otherwise it is not up (0). We set this rule in the M2 report and kept it for M3. A missing future price is not called up. Trading fees are ignored. The 15 rows dated September 26, 2026 stay out of Parts 2 through 5.")
    p(doc, "Class counts from the 510 labeled rows. Majority: up, 406 (79.6%). Minority: not up, 104 (20.4%).")

    heading(doc, "Part 1 — The notebook")
    p(doc, "Notebook link: https://colab.research.google.com/github/The0gCarrot/doge-defenders/blob/m3-exploratory/notebooks/M3_exploratory_analysis.ipynb")
    p(doc, "The file in the project is notebooks/M3_exploratory_analysis.ipynb. On Colab, Runtime → Restart and run all clones the m3-exploratory branch and reads data/processed/daily_reports.csv. Every number in this memo is printed by the notebook. Each analysis block has a markdown cell above it that says what the block does and why we ran it.")

    heading(doc, "Part 2 — Univariate and bivariate exploration")
    p(doc, "2.1  One variable at a time. These six numbers are the ones a manager would be tempted to quote. The mean and the median are both from the 510 labeled rows.", space_after=3)
    table(
        doc,
        ["Variable", "Mean", "Median", "Shape", "What the mean hides"],
        [
            ["Price", "$4,581", "$2.95", "Right skew 3.53", "BTC and ETH are 99.7% of summed prices. A typical coin costs about $3."],
            ["Dollar volume", "$3.59 billion", "$295 million", "Right skew 3.45", "The average day is about twelve times the middle day."],
            ["Market value", "$114.3 billion", "$3.86 billion", "Right skew 3.38", "Bitcoin is 78.0% of summed market value. The average describes Bitcoin."],
            ["30-day change", "−14.3%", "−18.1%", "Right skew 2.94", "The middle coin was down about 18%. Rallies up to +123% lift the average."],
            ["Headline count", "1.52", "0", "Right skew 1.77", "54.3% of rows have no headline. The average implies a story the middle day lacks."],
            ["24-hour return", "−0.76%", "−0.70%", "Skew 0.06", "The average does not mislead. A typical day was a small loss."],
        ],
    )
    picture(doc, "01_market_cap_distribution.png", 3.9)
    caption(doc, "Figure 1. Takeaway: half of the coin-days are worth under about $3.9 billion. The $114 billion average sits far to the right because a few very large coins, above all Bitcoin, pull it there. Quote the median when you describe a typical coin.")

    p(doc, "2.2  Each predictor against the result. For a number, we compare the median on the 406 up rows with the median on the 104 not-up rows. For a label, we report the share that finished up.", space_before=4, space_after=3)
    table(
        doc,
        ["Predictor", "How we compared", "What we see"],
        [
            ["30-day change", "Median by class; share up by quarter", "Median −20.4% when up, −5.4% when not. Weakest 128 rows: 125 up (97.7%). Strongest 128: 67 up (52.3%)."],
            ["Vs 30-day high", "Median by class", "Up rows were further below the high (median −23.6%) than not-up rows (−15.1%)."],
            ["Category", "Share that finished up", "DeFi 102/102. Layer 1 222/272 (81.6%). Meme 43/68 (63.2%). Smart contract 39/68 (57.4%). DeFi is only LINK, AAVE, and UNI."],
            ["Headline opinion", "Share that finished up", "No headline 229/277 (82.7%). Any headline 177/233 (76.0%). Bullish 62/78, bearish 26/34, neutral 89/121."],
            ["24-hour return", "Median by class", "−0.67% when up, −0.76% when not. Correlation with the result: −0.002."],
        ],
    )
    picture_pair(doc, "02_momentum_vs_target.png", "03_up_rate_by_date.png", 3.2)
    caption(doc, "Figure 2 (left). The best recent months were higher 90 days later 67 of 128 times. The worst months were higher 125 of 128 times. The chart rounds those shares. Figure 3 (right). June 2 was the low point (46.7% of 15 coins). Before June 10, 166 of 255 rows were higher (65.1%). From June 10 on, 240 of 255 were higher (94.1%). The dashed line is June 10.")

    heading(doc, "Part 3 — Correlation and similarity")
    p(doc, "3.1  The heatmap. The map uses the 510 labeled rows and nine numeric columns. It leaves out the 90-day result, the model scores, and the practice portfolio, because those are the answer or were built from it.")
    p(doc, "Strongest relationship 1: price and market value, correlation +0.990. Market value is price times the number of coins, so this line is mostly a definition, not a discovery.")
    p(doc, "Strongest relationship 2: dollar volume and market value, correlation +0.880. The next pair, price and dollar volume, is +0.838. The 30-day price change and the distance from the 30-day high move together at +0.632, which means those two \"decision facts\" are partly the same fact.")
    p(doc, "What the heatmap does not tell you. It does not say that one column causes another. It only notices straight lines. It leaves out category, exchange, and the headline text. It describes columns, not whether two coin-days are alike. And the darkest square is not the useful one for our question: the 30-day price change is almost unrelated to market value (about −0.01 on the map) but it is the strongest numeric link to the result (−0.409).")
    picture(doc, "04_correlation_heatmap.png", 3.7)
    caption(doc, "Figure 4. Takeaway: price, dollar volume, and market value are one cluster. Numbers are printed only where the correlation is at least 0.50 in absolute value. A red square is not a reason to buy.")

    p(doc, "3.2  Similarity. A row we would compare holds 9 numeric fields, 3 name fields (category, exchange, and headline opinion), a date, a list of up to 30 past prices, and free-text headlines. That is a mixed row. The fitting measure is Gower distance: on May 24, 2026, each numeric gap is divided by that field's range across the 15 coins, a matching name scores 0 and a mismatch scores 1, and every field counts once. Zero would mean the rows match. One would mean they share nothing.")
    p(doc, "Why not raw Euclidean distance. On May 24 the raw distance from Bitcoin to Pepe is about 1.54 trillion, and 99.96% of the squared distance is market value alone. Bitcoin to Ethereum is about 1.28 trillion, so the raw measure treats those pairs as similarly far apart. Gower scores Bitcoin–Ethereum at 0.218, Bitcoin–Pepe at 0.598, and Dogecoin–Pepe at 0.285. Jaccard would drop the dollar amounts. Cosine would fit the headlines only.")

    heading(doc, "Part 4 — Three business findings")
    p(doc, "4.1  Do not treat a strong recent month as a reason to buy. Evidence: Figure 2. The 128 rows with the weakest 30-day change finished higher 125 times. The 128 rows with the strongest 30-day change finished higher 67 times. Rows behind it: those 256 rows, inside the 510 labeled rows. A manager would stop using \"it just rallied\" as a buy signal in this book, and would read Part 5 before turning the chart into a rule.")
    p(doc, "4.2  Do not give Dogecoin and Pepe one meme budget. Evidence: Figure 5. Dogecoin was higher on 10 of its 34 labeled days (29.4%). Pepe was higher on 33 of 34 (97.1%). The meme average, 43 of 68 (63.2%), describes neither coin. Rows behind it: 68. A manager would size the two coins separately. The category word is not the position.")
    picture(doc, "05_up_rate_by_token.png", 3.5)
    caption(doc, "Figure 5. Takeaway: seven coins were higher on all 34 labeled days (Bitcoin, Ethereum, Solana, XRP, Chainlink, Uniswap, and Aave). Dogecoin, in rust, was the weakest name in the file. Pepe, in teal, was close to the perfect group. Both carry the meme label.")
    p(doc, "4.3  Do not let a headline overturn the price view in this file. Evidence: the opinion table in section 2.2. Days with no headline finished higher 229 of 277 times (82.7%). Days with at least one headline finished higher 177 of 233 times (76.0%). Bullish days (79.5%) and bearish days (76.5%) are close. Rows behind it: all 510 labeled rows. A manager would keep any news adjustment small. Tone, in this window, does not separate the coins that rose from the coins that did not.")

    heading(doc, "Part 5 — The surprise")
    p(doc, "What surprised us. We expected coins that had just risen to be the ones higher 90 days later. The strongest link to the result is the 30-day price change, and it points the other way (−0.409). The exciting explanation is that the market punished chasing and rewarded dips. The boring explanation is the calendar: later June dates were deeper in a selloff (the 30-day change correlates −0.360 with the date) and those same dates almost all finished up (the result correlates +0.404 with the date).")
    p(doc, "We believe the boring explanation is the main reason the full-file number looks so strong. We checked by splitting the 510 rows at June 10. Before that date the weakest quarter finished higher 60 of 64 times and the strongest quarter 28 of 64 times, so a gap remains early. On and after June 10 the weakest quarter was 64 of 64 and the strongest was 63 of 64. The late window does not show the pattern, because almost every coin finished up. We would not hand a manager Figure 2 as a standing rule.")

    heading(doc, "Required plots")
    p(doc, "Figure 1, distribution: the average coin is not the typical coin. Figure 2, relationship: the strongest recent months were least often higher 90 days later. Figure 3, time: late-June start dates almost all finished higher. Figure 4, heatmap: price, volume, and market value repeat one another. Figure 5, our own chart: Dogecoin and Pepe share a label and not an outcome.")

    heading(doc, "Part 6 — AI Collaboration Log")
    p(doc, "Copied forward from the Week 4 decision log in the M2 report. These are catches we checked, not a new log written for this memo.")
    p(doc, "Exchanges and categories. An assistant picked the biggest trading pair and CoinGecko's first tag. That made odd exchanges look like Bitcoin's home and treated fund names as business types. We checked the raw lists by hand. The file now uses Binance, KuCoin, and Coinbase International, and four types: Layer 1, DeFi, Meme, and Smart Contract Platform.")
    p(doc, "News source. An assistant called CoinGecko's status-update link. Every coin returned \"page not found.\" We repeated the calls, made up no headlines, and switched to GDELT and Yahoo. If the two sources disagree, the opinion is neutral and the score changes by 0.")
    p(doc, "Cleaning and prices. A draft wanted empty columns dropped, extreme prices cut, and the file rescaled before the test split. We kept every row, used −999, NULL, and N/A, and rescaled only inside the model after the split. A saved September 17 file priced Bitcoin near $76,608; a live check was about $84,000, so today's row uses the live price. \"Score divided by 10, as a percent of cash still left\" was our rule.")

    for path in OUTS:
        path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(path)
        print("Wrote", path)


if __name__ == "__main__":
    main()
