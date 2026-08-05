"""
Team Howe brand tokens.

Every value here was read directly off teamhowe.com (Luxury Presence
"masterpiece" theme) so the dashboard and the emails match the live site.

    --global-primary-font-family : Montserrat, sans-serif
    --global-secondary-font-family: Montserrat, sans-serif
    themeBlack                   : #211f1f
    themeBeige                   : #ccb091
    themeWhite                   : #fff
    --global-h1-font-size        : 45px   (h2 40 / h3 35 / h4 28 / h5 22 / h6 20)
    --global-body-font-size      : 16px
"""

# ---------------------------------------------------------------- colour ----
BLACK = "#211f1f"          # themeBlack - primary text and dark surfaces
INK = "#141414"             # deepest surface used on the site's hero sections
CHARCOAL = "#1a1a1a"
BEIGE = "#ccb091"          # themeBeige - the Team Howe accent
BEIGE_SOFT = "#d6beb3"
BEIGE_WASH = "#f6f0ea"     # tint of BEIGE for quiet backgrounds
WHITE = "#ffffff"
OFF_WHITE = "#f8f8f8"
GREY = "#848484"           # site's muted copy colour
GREY_LIGHT = "#b6b6b6"
BORDER = "#eeeeee"

# Status colours, kept desaturated so they sit inside the brand rather than
# fighting it.
HOT = "#8c2f27"
HOT_WASH = "#f9eeec"
LEAD = "#5c6b4a"
LEAD_WASH = "#f0f2ec"

# ------------------------------------------------------------ typography ----
FONT = "'Montserrat', -apple-system, BlinkMacSystemFont, 'Helvetica Neue', Arial, sans-serif"
FONT_STACK_EMAIL = "'Montserrat', 'Helvetica Neue', Helvetica, Arial, sans-serif"
GOOGLE_FONTS = (
    "https://fonts.googleapis.com/css2?"
    "family=Montserrat:wght@300;400;500;600;700&display=swap"
)

H1 = "45px"
H2 = "40px"
H3 = "35px"
H4 = "28px"
H5 = "22px"
H6 = "20px"
BODY = "16px"

# ----------------------------------------------------------------- assets ----
_CDN = "https://media-production.lp-cdn.com/cdn-cgi/image/format=auto,quality=85,fit=scale-down,width={w}/https://media-production.lp-cdn.com/media/{id}"
_LOGO_DARK_ID = "702d6c63-90ed-4078-b73e-10aa815f7905"   # black wordmark
_LOGO_LIGHT_ID = "da43fa44-b24f-4ae6-80bb-2450fcbe04e9"  # white wordmark


def logo(on_dark=True, width=960):
    """Team Howe | Compass lockup. White version for dark surfaces."""
    return _CDN.format(w=width, id=_LOGO_LIGHT_ID if on_dark else _LOGO_DARK_ID)


FAVICON = "https://teamhowe.com/favicon-32x32.png"

# ------------------------------------------------------------------ copy ----
TEAM_NAME = "Team Howe"
TAGLINE = "Remarkably Savvy. Refreshingly Honest."
PHONE = "(415) 640-4664"
PHONE_HREF = "tel:+14156404664"
ADDRESS = "3512 16th Street, San Francisco, CA 94114"
WEBSITE = "https://teamhowe.com"

LEGAL = (
    "Team Howe is a team of real estate agents affiliated with Compass. Compass is a "
    "real estate broker licensed by the State of California and abides by Equal Housing "
    "Opportunity laws. License Number 01527235. Sherri Howe CA DRE# 01816621. "
    "All material presented herein is intended for informational purposes only and is "
    "compiled from sources deemed reliable but has not been verified."
)


def copyright_line(year):
    """Note the deliberate space before 'Compass' - TJ flagged the missing one."""
    return "Copyright © {} {}. All Rights Reserved. ".format(year, TEAM_NAME)
