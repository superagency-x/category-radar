#!/bin/bash
# ==============================================================================
# Category Radar · Central Europe Category Intelligence Runner
# ==============================================================================

export PATH="$HOME/.local/bin:$HOME/.cargo/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

PROJECT_DIR="/Users/berksaraloglu/Projects/category-radar"
cd "$PROJECT_DIR" || exit 1

BOLD=$(tput bold 2>/dev/null || echo "")
NORMAL=$(tput sgr0 2>/dev/null || echo "")
BLUE=$(tput setaf 4 2>/dev/null || echo "")
CYAN=$(tput setaf 6 2>/dev/null || echo "")
GREEN=$(tput setaf 2 2>/dev/null || echo "")
YELLOW=$(tput setaf 3 2>/dev/null || echo "")
DIM=$(tput dim 2>/dev/null || echo "")

clear

echo "${BLUE}╔══════════════════════════════════════════════════════════════════════╗${NORMAL}"
echo "${BLUE}║${NORMAL}              ${BOLD}${CYAN}C A T E G O R Y   R A D A R${NORMAL}                             ${BLUE}║${NORMAL}"
echo "${BLUE}║${NORMAL}       ${DIM}Central Europe Market Intelligence & Retail Scraper${NORMAL}            ${BLUE}║${NORMAL}"
echo "${BLUE}╚══════════════════════════════════════════════════════════════════════╝${NORMAL}"
echo ""
echo "${BOLD}Target Category:${NORMAL} Air Fryers (Heißluftfritteusen)"
echo "${BOLD}Covered Markets:${NORMAL} Germany (DE) · Austria (AT) · Switzerland (CH)"
echo "                 Poland (PL) · Czechia (CZ) · Hungary (HU)"
echo "${BOLD}Retail Channels:${NORMAL} Geizhals (DE/AT) · MediaMarkt (DE) · Otto (DE)"
echo "                 Toppreise (CH) · Ceneo (PL) · Alza (CZ) · Árukereső (HU)"
echo ""
echo "${CYAN}──────────────────────────────────────────────────────────────────────${NORMAL}"
echo "  ${GREEN}[1] Run Full Live Scraper${NORMAL}  (Auto-starts in 5s...)"
echo "      Scrapes Central European markets, runs normalization,"
echo "      promotional intensity, editorial testing & opens dashboard"
echo ""
echo "  ${YELLOW}[2] Open Interactive Dashboard${NORMAL} (Instant view, no scraping)"
echo "      Launches local server at http://localhost:8000"
echo ""
echo "  ${BLUE}[3] View Executive Dossier${NORMAL} (Printable report & markdown)"
echo "      Opens the generated C-level category intelligence briefing"
echo ""
echo "  ${DIM}[4] Run Channel Diagnostics${NORMAL} (Health check on selectors)"
echo "${CYAN}──────────────────────────────────────────────────────────────────────${NORMAL}"
echo ""

CHOICE="1"
if read -t 5 -p "${BOLD}Select option [1-4] or press Enter to scrape:${NORMAL} " USER_INPUT; then
    if [ -n "$USER_INPUT" ]; then
        CHOICE="$USER_INPUT"
    fi
fi
echo ""

UV_BIN=$(which uv 2>/dev/null || echo "$HOME/.local/bin/uv")
if [ ! -x "$UV_BIN" ]; then
    echo "Error: 'uv' package manager not found. Please check your installation."
    read -p "Press Enter to exit..."
    exit 1
fi

case "$CHOICE" in
    1)
        echo "${GREEN}▶ Launching full multi-market scraper pipeline...${NORMAL}"
        echo "${DIM}(Polite crawl: respecting robots.txt, 4s delay per host)${NORMAL}"
        echo ""
        "$UV_BIN" run radar run
        SCRAPE_EXIT=$?
        echo ""
        if [ $SCRAPE_EXIT -eq 0 ]; then
            echo "${GREEN}✔ Scrape and analytics pipeline completed successfully!${NORMAL}"
            echo "${CYAN}▶ Launching interactive dashboard at http://localhost:8000 ...${NORMAL}"
            (sleep 1 && open "http://localhost:8000") &
            "$UV_BIN" run radar serve
        else
            echo "${YELLOW}Pipeline finished with code $SCRAPE_EXIT.${NORMAL}"
            read -p "Press Enter to close this window..."
        fi
        ;;
    2)
        echo "${CYAN}▶ Launching interactive dashboard at http://localhost:8000 ...${NORMAL}"
        (sleep 1 && open "http://localhost:8000") &
        "$UV_BIN" run radar serve
        ;;
    3)
        echo "${BLUE}▶ Generating and opening executive category intelligence dossier...${NORMAL}"
        "$UV_BIN" run radar report
        LATEST_HTML=$(ls -t data/exports/executive_brief_*.html 2>/dev/null | head -1)
        if [ -n "$LATEST_HTML" ]; then
            open "$LATEST_HTML"
        fi
        echo ""
        read -p "Press Enter to close this window..."
        ;;
    4)
        echo "${DIM}▶ Running doctor diagnostics across all channels...${NORMAL}"
        "$UV_BIN" run radar doctor
        echo ""
        read -p "Press Enter to close this window..."
        ;;
    *)
        echo "Invalid selection. Exiting."
        sleep 2
        ;;
esac
