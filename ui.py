# ui.py
import io
from typing import Dict, Any

import wx
import requests

from firebase_auth import FirebaseAuthClient, FirebaseAuthError
from omdb_client import search_movies, get_movie_details, OMDbError
from ai_client import get_movie_insights, is_enabled as ai_enabled


# =============== THEME SYSTEM =============== #

class Theme:
    def __init__(self, name, bg_window, bg_surface, bg_nav, bg_chip,
                 fg_primary, fg_muted, accent, accent_soft):
        self.name = name
        self.bg_window = bg_window
        self.bg_surface = bg_surface
        self.bg_nav = bg_nav
        self.bg_chip = bg_chip
        self.fg_primary = fg_primary
        self.fg_muted = fg_muted
        self.accent = accent
        self.accent_soft = accent_soft


DARK_THEME = Theme(
    "dark",
    bg_window=wx.Colour(12, 12, 16),
    bg_surface=wx.Colour(24, 24, 32),
    bg_nav=wx.Colour(10, 10, 14),
    bg_chip=wx.Colour(40, 40, 55),
    fg_primary=wx.Colour(240, 240, 245),
    fg_muted=wx.Colour(160, 160, 175),
    accent=wx.Colour(0, 120, 215),
    accent_soft=wx.Colour(35, 75, 130),
)

LIGHT_THEME = Theme(
    "light",
    bg_window=wx.Colour(245, 245, 248),
    bg_surface=wx.Colour(255, 255, 255),
    bg_nav=wx.Colour(240, 240, 245),
    bg_chip=wx.Colour(230, 230, 240),
    fg_primary=wx.Colour(25, 25, 30),
    fg_muted=wx.Colour(90, 90, 110),
    accent=wx.Colour(0, 120, 215),
    accent_soft=wx.Colour(200, 220, 245),
)

CURRENT_THEME = DARK_THEME  # default: streaming vibes


def set_theme(name: str):
    global CURRENT_THEME
    if name.lower() == "light":
        CURRENT_THEME = LIGHT_THEME
    else:
        CURRENT_THEME = DARK_THEME


class LoadingOverlay:
    """
    Simple context manager to show a 'Loading...' overlay + busy cursor
    during long operations (HTTP calls, etc.).
    Usage:
        with LoadingOverlay(self, "Signing in..."):
            do_network_stuff()
    """
    def __init__(self, parent: wx.Window, message: str = "Loading..."):
        self.parent = parent
        self.message = message
        self._info = None

    def __enter__(self):
        wx.BeginBusyCursor()
        self._info = wx.BusyInfo(self.message, parent=self.parent)
        wx.Yield()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._info:
            del self._info
            self._info = None
        if wx.IsBusy():
            wx.EndBusyCursor()
        wx.Yield()


# =============== MOVIE TILE =============== #

class MovieTile(wx.Panel):
    """
    Poster card used in the search wall.
    """
    POSTER_W = 130
    POSTER_H = 190

    def __init__(self, parent: wx.Window, movie: Dict[str, Any], on_click):
        super().__init__(parent)
        self.movie = movie
        self.on_click = on_click

        self.SetBackgroundColour(CURRENT_THEME.bg_surface)

        vbox = wx.BoxSizer(wx.VERTICAL)

        # Poster
        self.poster = wx.StaticBitmap(self, size=(self.POSTER_W, self.POSTER_H))
        self._load_poster()

        # Title + year
        title = movie.get("Title", "Unknown")
        year = movie.get("Year", "")
        title_lbl = wx.StaticText(self, label=title, style=wx.ST_NO_AUTORESIZE)
        tfont = title_lbl.GetFont()
        tfont = tfont.Bold()
        title_lbl.SetFont(tfont)
        title_lbl.SetForegroundColour(CURRENT_THEME.fg_primary)
        title_lbl.Wrap(self.POSTER_W)

        year_lbl = wx.StaticText(self, label=year)
        year_lbl.SetForegroundColour(CURRENT_THEME.fg_muted)

        vbox.Add(self.poster, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 4)
        vbox.Add(title_lbl, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.ALIGN_CENTER_HORIZONTAL, 4)
        vbox.Add(year_lbl, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 2)

        self.SetSizer(vbox)

        # Hover / click
        self.Bind(wx.EVT_ENTER_WINDOW, self._on_hover_enter)
        self.Bind(wx.EVT_LEAVE_WINDOW, self._on_hover_leave)
        for ctrl in (self, self.poster, title_lbl, year_lbl):
            ctrl.Bind(wx.EVT_LEFT_DOWN, self._on_click)

    def _load_poster(self):
        url = self.movie.get("Poster")
        if not url or url == "N/A":
            return
        try:
            resp = requests.get(url, timeout=5)
            img_data = resp.content
            image = wx.Image(io.BytesIO(img_data))
            image = image.Scale(self.POSTER_W, self.POSTER_H, wx.IMAGE_QUALITY_HIGH)
            bmp = wx.Bitmap(image)
            self.poster.SetBitmap(bmp)
        except Exception:
            pass

    def _on_click(self, event):
        if callable(self.on_click):
            self.on_click(self.movie)

    def _on_hover_enter(self, event):
        self.SetBackgroundColour(CURRENT_THEME.bg_chip)
        self.Refresh()
        event.Skip()

    def _on_hover_leave(self, event):
        self.SetBackgroundColour(CURRENT_THEME.bg_surface)
        self.Refresh()
        event.Skip()


# =============== SETTINGS DIALOG =============== #

class SettingsDialog(wx.Dialog):
    def __init__(self, parent, auth_client: FirebaseAuthClient, on_theme_change):
        super().__init__(parent, title="Settings", size=(440, 320))

        self.auth_client = auth_client
        self.on_theme_change = on_theme_change

        panel = wx.Panel(self)
        panel.SetBackgroundColour(CURRENT_THEME.bg_surface)

        nb = wx.Notebook(panel)

        # Appearance tab
        appearance_panel = wx.Panel(nb)
        appearance_panel.SetBackgroundColour(CURRENT_THEME.bg_surface)
        a_sizer = wx.BoxSizer(wx.VERTICAL)

        a_label = wx.StaticText(appearance_panel, label="Appearance")
        a_font = a_label.GetFont()
        a_font = a_font.Bold()
        a_label.SetFont(a_font)
        a_label.SetForegroundColour(CURRENT_THEME.fg_primary)

        self.radio_dark = wx.RadioButton(
            appearance_panel, label="Dark (recommended)", style=wx.RB_GROUP
        )
        self.radio_light = wx.RadioButton(appearance_panel, label="Light")

        # Set current
        if CURRENT_THEME.name == "dark":
            self.radio_dark.SetValue(True)
        else:
            self.radio_light.SetValue(True)

        for rb in (self.radio_dark, self.radio_light):
            rb.SetForegroundColour(CURRENT_THEME.fg_primary)
            rb.SetBackgroundColour(CURRENT_THEME.bg_surface)

        a_sizer.Add(a_label, 0, wx.ALL, 10)
        a_sizer.Add(self.radio_dark, 0, wx.LEFT | wx.TOP, 15)
        a_sizer.Add(self.radio_light, 0, wx.LEFT | wx.TOP | wx.BOTTOM, 15)

        appearance_panel.SetSizer(a_sizer)

        # Account tab
        account_panel = wx.Panel(nb)
        account_panel.SetBackgroundColour(CURRENT_THEME.bg_surface)
        ac_sizer = wx.BoxSizer(wx.VERTICAL)

        ac_label = wx.StaticText(account_panel, label="Account")
        ac_font = ac_label.GetFont()
        ac_font = ac_font.Bold()
        ac_label.SetFont(ac_font)
        ac_label.SetForegroundColour(CURRENT_THEME.fg_primary)

        email = self.auth_client.user.get("email") if self.auth_client.user else "Unknown"
        email_lbl = wx.StaticText(account_panel, label=f"Signed in as: {email}")
        email_lbl.SetForegroundColour(CURRENT_THEME.fg_muted)

        btn_logout = wx.Button(account_panel, label="Sign Out")

        ac_sizer.Add(ac_label, 0, wx.ALL, 10)
        ac_sizer.Add(email_lbl, 0, wx.ALL, 10)
        ac_sizer.Add(btn_logout, 0, wx.ALL | wx.ALIGN_LEFT, 10)

        account_panel.SetSizer(ac_sizer)

        nb.AddPage(appearance_panel, "Appearance")
        nb.AddPage(account_panel, "Account")

        # Bottom buttons
        btns = self.CreateSeparatedButtonSizer(wx.OK | wx.CANCEL)

        # Layout
        root = wx.BoxSizer(wx.VERTICAL)
        root.Add(nb, 1, wx.EXPAND | wx.ALL, 10)
        if btns:
            root.Add(btns, 0, wx.EXPAND | wx.ALL, 5)

        panel.SetSizer(root)

        # Events
        btn_logout.Bind(wx.EVT_BUTTON, self.on_logout)

    def on_logout(self, event):
        self.auth_client.sign_out()
        wx.MessageBox("Signed out. Restart the app to log in again.", "Sign Out",
                      wx.OK | wx.ICON_INFORMATION, parent=self)


# =============== LOGIN FRAME =============== #

class LoginFrame(wx.Frame):
    def __init__(self, parent=None, title="CineBy – Sign in"):
        super().__init__(parent, title=title, size=(460, 330))
        self.auth_client = FirebaseAuthClient()

        self.SetBackgroundColour(CURRENT_THEME.bg_window)
        panel = wx.Panel(self)
        panel.SetBackgroundColour(CURRENT_THEME.bg_surface)

        outer = wx.BoxSizer(wx.VERTICAL)

        # Branding
        brand_panel = wx.Panel(panel)
        brand_panel.SetBackgroundColour(CURRENT_THEME.bg_surface)
        b_sizer = wx.BoxSizer(wx.HORIZONTAL)

        logo = wx.StaticText(brand_panel, label="CineBy")
        lfont = logo.GetFont()
        lfont.PointSize += 8
        lfont = lfont.Bold()
        logo.SetFont(lfont)
        logo.SetForegroundColour(CURRENT_THEME.accent)

        tagline = wx.StaticText(brand_panel, label="Your AI-powered movie shelf")
        tagline.SetForegroundColour(CURRENT_THEME.fg_muted)

        text_sizer = wx.BoxSizer(wx.VERTICAL)
        text_sizer.Add(logo, 0, wx.BOTTOM, 2)
        text_sizer.Add(tagline, 0)

        icon = wx.StaticBitmap(
            brand_panel,
            bitmap=wx.ArtProvider.GetBitmap(wx.ART_NORMAL_FILE, wx.ART_OTHER, (32, 32))
        )

        b_sizer.Add(icon, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        b_sizer.Add(text_sizer, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        brand_panel.SetSizer(b_sizer)

        # Form
        form = wx.Panel(panel)
        form.SetBackgroundColour(CURRENT_THEME.bg_surface)
        f_sizer = wx.BoxSizer(wx.VERTICAL)

        self.email_txt = wx.TextCtrl(form, style=wx.TE_PROCESS_ENTER)
        self.email_txt.SetHint("Email")

        self.password_txt = wx.TextCtrl(
            form,
            style=wx.TE_PASSWORD | wx.TE_PROCESS_ENTER
        )
        self.password_txt.SetHint("Password")

        btn_row = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_login = wx.Button(form, label="Sign In")
        self.btn_signup = wx.Button(form, label="Create Account")

        self.btn_login.SetBackgroundColour(CURRENT_THEME.accent)
        self.btn_login.SetForegroundColour(wx.Colour(255, 255, 255))

        btn_row.Add(self.btn_login, 1, wx.ALL | wx.EXPAND, 4)
        btn_row.Add(self.btn_signup, 1, wx.ALL | wx.EXPAND, 4)

        f_sizer.Add(self.email_txt, 0, wx.ALL | wx.EXPAND, 6)
        f_sizer.Add(self.password_txt, 0, wx.ALL | wx.EXPAND, 6)
        f_sizer.Add(btn_row, 0, wx.ALL | wx.EXPAND, 2)

        form.SetSizer(f_sizer)

        outer.Add(brand_panel, 0, wx.EXPAND | wx.ALL, 10)
        outer.Add(form, 1, wx.EXPAND | wx.ALL, 10)

        panel.SetSizer(outer)

        # Events
        self.btn_login.Bind(wx.EVT_BUTTON, self.on_login)
        self.btn_signup.Bind(wx.EVT_BUTTON, self.on_signup)
        self.email_txt.Bind(wx.EVT_TEXT_ENTER, self.on_login)
        self.password_txt.Bind(wx.EVT_TEXT_ENTER, self.on_login)

        self.Centre()
        self.Show()

    def _do_auth(self, mode: str):
        email = self.email_txt.GetValue().strip()
        password = self.password_txt.GetValue().strip()

        if not email or not password:
            wx.MessageBox("Email and password required", "Validation",
                          wx.OK | wx.ICON_WARNING, parent=self)
            return

        try:
            with LoadingOverlay(self, "Contacting Firebase..."):
                if mode == "login":
                    self.auth_client.sign_in(email, password)
                else:
                    self.auth_client.sign_up(email, password)
        except FirebaseAuthError as e:
            wx.MessageBox(str(e), "Auth Error", wx.OK | wx.ICON_ERROR, parent=self)
            return

        # open main app
        self.Hide()
        main = MainFrame(auth_client=self.auth_client)
        main.Show()
        self.Destroy()

    def on_login(self, event):
        self._do_auth("login")

    def on_signup(self, event):
        self._do_auth("signup")


# =============== MAIN APP FRAME =============== #

class MainFrame(wx.Frame):
    def __init__(self, parent=None, title="CineBy", auth_client: FirebaseAuthClient = None):
        super().__init__(parent, title=title, size=(1200, 720))
        self.auth_client = auth_client or FirebaseAuthClient()
        self.current_movie: Dict[str, Any] = {}
        self.search_results = []

        self.SetBackgroundColour(CURRENT_THEME.bg_window)

        panel = wx.Panel(self)
        panel.SetBackgroundColour(CURRENT_THEME.bg_window)

        root = wx.BoxSizer(wx.VERTICAL)

        # ---------- TOP NAVBAR ---------- #
        nav = wx.Panel(panel)
        nav.SetBackgroundColour(CURRENT_THEME.bg_nav)
        nav_sizer = wx.BoxSizer(wx.HORIZONTAL)

        logo = wx.StaticText(nav, label="CineBy")
        lfont = logo.GetFont()
        lfont.PointSize += 4
        lfont = lfont.Bold()
        logo.SetFont(lfont)
        logo.SetForegroundColour(CURRENT_THEME.accent)

        nav_sizer.Add(logo, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 10)

        # center search bar
        nav_sizer.AddSpacer(20)
        self.search_ctrl = wx.SearchCtrl(nav, style=wx.TE_PROCESS_ENTER)
        self.search_ctrl.SetDescriptiveText("Search movies, shows...")
        self.search_ctrl.ShowCancelButton(True)
        nav_sizer.Add(self.search_ctrl, 1, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 10)

        # nav buttons (watchlist + settings)
        nav_sizer.AddSpacer(10)

        self.btn_watch_nav = wx.BitmapButton(
            nav,
            bitmap=wx.ArtProvider.GetBitmap(wx.ART_LIST_VIEW, wx.ART_TOOLBAR, (18, 18)),
            style=wx.BORDER_NONE
        )
        self.btn_settings = wx.BitmapButton(
            nav,
            bitmap=wx.ArtProvider.GetBitmap(wx.ART_HELP_SETTINGS, wx.ART_TOOLBAR, (18, 18)),
            style=wx.BORDER_NONE
        )

        nav_sizer.Add(self.btn_watch_nav, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 8)
        nav_sizer.Add(self.btn_settings, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 8)

        nav.SetSizer(nav_sizer)

        # ---------- HERO + RESULTS AREA ---------- #
        body = wx.Panel(panel)
        body.SetBackgroundColour(CURRENT_THEME.bg_window)
        body_sizer = wx.BoxSizer(wx.VERTICAL)

        # HERO SECTION
        hero = wx.Panel(body)
        hero.SetBackgroundColour(CURRENT_THEME.bg_surface)
        hero_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.hero_poster = wx.StaticBitmap(hero, size=(260, 380))

        hero_text_panel = wx.Panel(hero)
        hero_text_panel.SetBackgroundColour(CURRENT_THEME.bg_surface)
        ht_sizer = wx.BoxSizer(wx.VERTICAL)

        self.hero_title = wx.StaticText(hero_text_panel, label="Search for something to begin")
        hfont = self.hero_title.GetFont()
        hfont.PointSize += 4
        hfont = hfont.Bold()
        self.hero_title.SetFont(hfont)
        self.hero_title.SetForegroundColour(CURRENT_THEME.fg_primary)

        self.hero_meta = wx.StaticText(hero_text_panel, label="")
        self.hero_meta.SetForegroundColour(CURRENT_THEME.fg_muted)

        self.hero_plot = wx.TextCtrl(
            hero_text_panel,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_WORDWRAP
        )
        self.hero_plot.SetBackgroundColour(CURRENT_THEME.bg_surface)
        self.hero_plot.SetForegroundColour(CURRENT_THEME.fg_primary)

        btn_row = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_add_watch = wx.Button(hero_text_panel, label="Add to Watchlist")
        self.btn_ai = wx.Button(hero_text_panel, label="AI Insights") if ai_enabled() else None

        self.btn_add_watch.SetBackgroundColour(CURRENT_THEME.accent)
        self.btn_add_watch.SetForegroundColour(wx.Colour(255, 255, 255))

        btn_row.Add(self.btn_add_watch, 0, wx.ALL, 4)
        if self.btn_ai:
            self.btn_ai.SetBackgroundColour(CURRENT_THEME.accent_soft)
            self.btn_ai.SetForegroundColour(wx.Colour(255, 255, 255))
            btn_row.Add(self.btn_ai, 0, wx.ALL, 4)

        ht_sizer.Add(self.hero_title, 0, wx.ALL | wx.EXPAND, 5)
        ht_sizer.Add(self.hero_meta, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 5)
        ht_sizer.Add(self.hero_plot, 1, wx.ALL | wx.EXPAND, 5)
        ht_sizer.Add(btn_row, 0, wx.ALL, 5)

        hero_text_panel.SetSizer(ht_sizer)

        hero_sizer.Add(self.hero_poster, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 10)
        hero_sizer.Add(hero_text_panel, 1, wx.ALL | wx.EXPAND, 10)

        hero.SetSizer(hero_sizer)

        # RESULTS WALL
        wall_panel = wx.Panel(body)
        wall_panel.SetBackgroundColour(CURRENT_THEME.bg_window)
        wall_sizer = wx.BoxSizer(wx.VERTICAL)

        wall_label = wx.StaticText(wall_panel, label="Results")
        wl_font = wall_label.GetFont()
        wl_font = wl_font.Bold()
        wall_label.SetFont(wl_font)
        wall_label.SetForegroundColour(CURRENT_THEME.fg_primary)

        self.results_scrolled = wx.ScrolledWindow(
            wall_panel, style=wx.VSCROLL | wx.HSCROLL
        )
        self.results_scrolled.SetScrollRate(10, 10)
        self.results_scrolled.SetBackgroundColour(CURRENT_THEME.bg_window)

        self.results_sizer = wx.WrapSizer(orient=wx.HORIZONTAL)
        self.results_scrolled.SetSizer(self.results_sizer)

        wall_sizer.Add(wall_label, 0, wx.ALL, 8)
        wall_sizer.Add(self.results_scrolled, 1, wx.ALL | wx.EXPAND, 0)
        wall_panel.SetSizer(wall_sizer)

        body_sizer.Add(hero, 0, wx.ALL | wx.EXPAND, 10)
        body_sizer.Add(wall_panel, 1, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)

        body.SetSizer(body_sizer)

        # root layout
        root.Add(nav, 0, wx.EXPAND)
        root.Add(body, 1, wx.EXPAND)
        panel.SetSizer(root)

        # ---------- EVENT BINDINGS ---------- #
        self.search_ctrl.Bind(wx.EVT_TEXT_ENTER, self.on_search)
        self.search_ctrl.Bind(wx.EVT_SEARCHCTRL_SEARCH_BTN, self.on_search)
        self.search_ctrl.Bind(wx.EVT_SEARCHCTRL_CANCEL_BTN, self.on_clear_search)

        self.btn_add_watch.Bind(wx.EVT_BUTTON, self.on_add_watchlist)
        self.btn_watch_nav.Bind(wx.EVT_BUTTON, self.on_show_watchlist)
        self.btn_settings.Bind(wx.EVT_BUTTON, self.on_open_settings)

        if self.btn_ai:
            self.btn_ai.Bind(wx.EVT_BUTTON, self.on_ai_insights)

        self.Centre()

    # ---------- SEARCH LOGIC ---------- #

    def on_clear_search(self, event):
        self.search_ctrl.SetValue("")
        self.clear_results()

    def clear_results(self):
        for child in self.results_scrolled.GetChildren():
            child.Destroy()
        self.results_sizer.Layout()
        self.results_scrolled.Layout()
        self.results_scrolled.FitInside()

    def on_search(self, event):
        query = self.search_ctrl.GetValue().strip()
        if not query:
            wx.MessageBox("Enter a title to search.", "Search",
                          wx.OK | wx.ICON_INFORMATION, parent=self)
            return

        self.clear_results()

        try:
            with LoadingOverlay(self, "Searching OMDb..."):
                results = search_movies(query=query, page=1)
        except OMDbError as e:
            wx.MessageBox(str(e), "OMDb Error", wx.OK | wx.ICON_ERROR, parent=self)
            return

        if not results:
            wx.MessageBox("No results found.", "Search",
                          wx.OK | wx.ICON_INFORMATION, parent=self)
            return

        self.search_results = results

        for movie in results:
            tile = MovieTile(self.results_scrolled, movie, on_click=self.on_movie_tile_clicked)
            self.results_sizer.Add(tile, 0, wx.ALL, 8)

        self.results_scrolled.Layout()
        self.results_scrolled.FitInside()

    def on_movie_tile_clicked(self, movie: Dict[str, Any]):
        imdb_id = movie.get("imdbID")
        if not imdb_id:
            return

        try:
            with LoadingOverlay(self, "Loading details..."):
                details = get_movie_details(imdb_id=imdb_id)
        except OMDbError as e:
            wx.MessageBox(str(e), "OMDb Error", wx.OK | wx.ICON_ERROR, parent=self)
            return

        self.current_movie = details
        self.update_hero(details)

    # ---------- HERO UPDATE ---------- #

    def update_hero(self, movie: Dict[str, Any]):
        title = movie.get("Title", "Unknown")
        year = movie.get("Year", "")
        rating = movie.get("imdbRating", "N/A")
        runtime = movie.get("Runtime", "")
        genre = movie.get("Genre", "")

        self.hero_title.SetLabel(f"{title} ({year})")
        meta_parts = []
        if rating and rating != "N/A":
            meta_parts.append(f"★ {rating}")
        if runtime:
            meta_parts.append(runtime)
        if genre:
            meta_parts.append(genre)
        self.hero_meta.SetLabel(" • ".join(meta_parts))

        self.hero_plot.SetValue(movie.get("Plot", "No plot available."))

        poster_url = movie.get("Poster")
        if poster_url and poster_url != "N/A":
            try:
                resp = requests.get(poster_url, timeout=5)
                img_data = resp.content
                image = wx.Image(io.BytesIO(img_data))
                image = image.Scale(260, 380, wx.IMAGE_QUALITY_HIGH)
                bmp = wx.Bitmap(image)
                self.hero_poster.SetBitmap(bmp)
            except Exception:
                pass

        self.Layout()

    # ---------- WATCHLIST ---------- #

    def on_add_watchlist(self, event):
        if not self.current_movie:
            wx.MessageBox("Select a movie first.", "Watchlist",
                          wx.OK | wx.ICON_INFORMATION, parent=self)
            return

        imdb_id = self.current_movie.get("imdbID")
        if not imdb_id:
            wx.MessageBox("Missing imdbID – cannot save.", "Watchlist",
                          wx.OK | wx.ICON_ERROR, parent=self)
            return

        data = {
            "Title": self.current_movie.get("Title"),
            "Year": self.current_movie.get("Year"),
            "Type": self.current_movie.get("Type"),
            "imdbID": imdb_id,
        }

        try:
            self.auth_client.add_to_watchlist(imdb_id, data)
        except FirebaseAuthError as e:
            wx.MessageBox(str(e), "Watchlist Error", wx.OK | wx.ICON_ERROR, parent=self)
            return

        wx.MessageBox("Added to watchlist.", "Watchlist",
                      wx.OK | wx.ICON_INFORMATION, parent=self)

    def on_show_watchlist(self, event):
        try:
            watchlist = self.auth_client.get_watchlist()
        except FirebaseAuthError as e:
            wx.MessageBox(str(e), "Watchlist Error", wx.OK | wx.ICON_ERROR, parent=self)
            return

        if not watchlist:
            wx.MessageBox("Your watchlist is empty.", "Watchlist",
                          wx.OK | wx.ICON_INFORMATION, parent=self)
            return

        items = []
        for imdb_id, movie in watchlist.items():
            items.append(f"{movie.get('Title', 'Unknown')} ({movie.get('Year', '')}) [{imdb_id}]")

        dlg = wx.Dialog(self, title="Watchlist", size=(420, 360))
        p = wx.Panel(dlg)
        s = wx.BoxSizer(wx.VERTICAL)
        txt = wx.TextCtrl(p, value="\n".join(items),
                          style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_WORDWRAP)
        s.Add(txt, 1, wx.ALL | wx.EXPAND, 8)
        p.SetSizer(s)
        dlg.Centre()
        dlg.ShowModal()
        dlg.Destroy()

    # ---------- AI INSIGHTS ---------- #

    def on_ai_insights(self, event):
        if not self.current_movie:
            wx.MessageBox("Select a movie first.", "AI",
                          wx.OK | wx.ICON_INFORMATION, parent=self)
            return

        title = self.current_movie.get("Title", "Unknown")
        plot = self.current_movie.get("Plot", "")

        try:
            with LoadingOverlay(self, f"Asking AI about {title}..."):
                text = get_movie_insights(title, plot)
        except Exception as e:
            wx.MessageBox(str(e), "AI Error", wx.OK | wx.ICON_ERROR, parent=self)
            return

        dlg = wx.Dialog(self, title=f"AI Insights – {title}", size=(600, 420))
        p = wx.Panel(dlg)
        s = wx.BoxSizer(wx.VERTICAL)
        txt = wx.TextCtrl(p, value=text,
                          style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_WORDWRAP)
        s.Add(txt, 1, wx.ALL | wx.EXPAND, 8)
        p.SetSizer(s)
        dlg.Centre()
        dlg.ShowModal()
        dlg.Destroy()

    # ---------- SETTINGS ---------- #

    def on_open_settings(self, event):
        dlg = SettingsDialog(self, self.auth_client, on_theme_change=self.apply_theme_change)
        if dlg.ShowModal() == wx.ID_OK:
            # check theme selection
            new_theme = "dark" if dlg.radio_dark.GetValue() else "light"
            self.apply_theme_change(new_theme)
        dlg.Destroy()

    def apply_theme_change(self, theme_name: str):
        set_theme(theme_name)
        # Easiest: recreate the whole frame with new theme
        email_user = self.auth_client.user  # keep session
        self.Hide()
        new_frame = MainFrame(auth_client=self.auth_client)
        new_frame.Show()
        self.Destroy()
