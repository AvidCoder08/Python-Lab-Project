# ui.py
import io
from typing import Dict, Any

import wx
import requests

from firebase_auth import FirebaseAuthClient, FirebaseAuthError
from omdb_client import search_movies, get_movie_details, OMDbError
from ai_client import get_movie_insights, is_enabled as ai_enabled


# --------- LOGIN / SIGNUP FRAME --------- #

class LoginFrame(wx.Frame):
    def __init__(self, parent=None, title="MovieDB Login"):
        super().__init__(parent, title=title, size=(400, 300))
        self.auth_client = FirebaseAuthClient()
        panel = wx.Panel(self)

        vbox = wx.BoxSizer(wx.VERTICAL)

        title_lbl = wx.StaticText(panel, label="MovieDB")
        font = title_lbl.GetFont()
        font.PointSize += 6
        font = font.Bold()
        title_lbl.SetFont(font)

        self.email_txt = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.email_txt.SetHint("Email")

        self.password_txt = wx.TextCtrl(panel, style=wx.TE_PASSWORD)
        self.password_txt.SetHint("Password")

        btn_login = wx.Button(panel, label="Sign In")
        btn_signup = wx.Button(panel, label="Sign Up")

        vbox.Add(title_lbl, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 10)
        vbox.Add(self.email_txt, 0, wx.ALL | wx.EXPAND, 10)
        vbox.Add(self.password_txt, 0, wx.ALL | wx.EXPAND, 10)
        vbox.Add(btn_login, 0, wx.ALL | wx.EXPAND, 10)
        vbox.Add(btn_signup, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)

        panel.SetSizer(vbox)

        btn_login.Bind(wx.EVT_BUTTON, self.on_login)
        btn_signup.Bind(wx.EVT_BUTTON, self.on_signup)

        self.Centre()
        self.Show()

    def _do_auth(self, mode: str):
        email = self.email_txt.GetValue().strip()
        password = self.password_txt.GetValue().strip()

        if not email or not password:
            wx.MessageBox("Email and password required", "Validation", wx.OK | wx.ICON_WARNING)
            return

        try:
            if mode == "login":
                self.auth_client.sign_in(email, password)
            else:
                self.auth_client.sign_up(email, password)
        except FirebaseAuthError as e:
            wx.MessageBox(str(e), "Auth Error", wx.OK | wx.ICON_ERROR)
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


# --------- MAIN APP FRAME --------- #

class MainFrame(wx.Frame):
    def __init__(self, parent=None, title="MovieDB", auth_client: FirebaseAuthClient = None):
        super().__init__(parent, title=title, size=(900, 600))
        self.auth_client = auth_client or FirebaseAuthClient()
        self.current_movie: Dict[str, Any] = {}

        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Left side: search + results
        left_panel = wx.Panel(panel)
        left_sizer = wx.BoxSizer(wx.VERTICAL)

        search_box_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.search_txt = wx.TextCtrl(left_panel)
        self.search_txt.SetHint("Search movie title...")
        btn_search = wx.Button(left_panel, label="Search")
        search_box_sizer.Add(self.search_txt, 1, wx.ALL | wx.EXPAND, 5)
        search_box_sizer.Add(btn_search, 0, wx.ALL, 5)

        self.results_list = wx.ListCtrl(left_panel, style=wx.LC_REPORT)
        self.results_list.InsertColumn(0, "Title", width=220)
        self.results_list.InsertColumn(1, "Year", width=70)
        self.results_list.InsertColumn(2, "Type", width=80)
        self.results_list.InsertColumn(3, "imdbID", width=100)

        left_sizer.Add(search_box_sizer, 0, wx.EXPAND)
        left_sizer.Add(self.results_list, 1, wx.ALL | wx.EXPAND, 5)
        left_panel.SetSizer(left_sizer)

        # Right side: details + actions
        right_panel = wx.Panel(panel)
        right_sizer = wx.BoxSizer(wx.VERTICAL)

        self.title_lbl = wx.StaticText(right_panel, label="Select a movie")
        title_font = self.title_lbl.GetFont()
        title_font.PointSize += 4
        title_font = title_font.Bold()
        self.title_lbl.SetFont(title_font)

        self.poster_bitmap = wx.StaticBitmap(right_panel, size=(300, 400))
        self.plot_txt = wx.TextCtrl(
            right_panel,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_WORDWRAP
        )

        btn_watchlist = wx.Button(right_panel, label="Add to Watchlist")
        btn_show_watchlist = wx.Button(right_panel, label="Show Watchlist")

        if ai_enabled():
            self.btn_ai = wx.Button(right_panel, label="AI Insights")
        else:
            self.btn_ai = None

        right_sizer.Add(self.title_lbl, 0, wx.ALL | wx.EXPAND, 5)
        right_sizer.Add(self.poster_bitmap, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 5)
        right_sizer.Add(self.plot_txt, 1, wx.ALL | wx.EXPAND, 5)
        right_sizer.Add(btn_watchlist, 0, wx.ALL | wx.EXPAND, 5)
        right_sizer.Add(btn_show_watchlist, 0, wx.ALL | wx.EXPAND, 5)
        if self.btn_ai:
            right_sizer.Add(self.btn_ai, 0, wx.ALL | wx.EXPAND, 5)

        right_panel.SetSizer(right_sizer)

        main_sizer.Add(left_panel, 1, wx.EXPAND)
        main_sizer.Add(right_panel, 1, wx.EXPAND)
        panel.SetSizer(main_sizer)

        # Bind events
        btn_search.Bind(wx.EVT_BUTTON, self.on_search)
        self.results_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_select_movie)
        btn_watchlist.Bind(wx.EVT_BUTTON, self.on_add_watchlist)
        btn_show_watchlist.Bind(wx.EVT_BUTTON, self.on_show_watchlist)
        if self.btn_ai:
            self.btn_ai.Bind(wx.EVT_BUTTON, self.on_ai_insights)

        self.Centre()

    # ---------- SEARCH LOGIC ----------

    def on_search(self, event):
        query = self.search_txt.GetValue().strip()
        if not query:
            wx.MessageBox("Enter a movie title to search", "Validation", wx.OK | wx.ICON_WARNING)
            return

        self.results_list.DeleteAllItems()
        try:
            results = search_movies(query=query, page=1)
        except OMDbError as e:
            wx.MessageBox(str(e), "OMDb Error", wx.OK | wx.ICON_ERROR)
            return

        for movie in results:
            idx = self.results_list.InsertItem(self.results_list.GetItemCount(), movie.get("Title", ""))
            self.results_list.SetItem(idx, 1, movie.get("Year", ""))
            self.results_list.SetItem(idx, 2, movie.get("Type", ""))
            self.results_list.SetItem(idx, 3, movie.get("imdbID", ""))

    # ---------- MOVIE DETAILS ----------

    def on_select_movie(self, event):
        index = event.GetIndex()
        imdb_id = self.results_list.GetItem(index, 3).GetText()
        try:
            movie = get_movie_details(imdb_id=imdb_id)
        except OMDbError as e:
            wx.MessageBox(str(e), "OMDb Error", wx.OK | wx.ICON_ERROR)
            return

        self.current_movie = movie
        self.update_movie_details(movie)

    def update_movie_details(self, movie: Dict[str, Any]):
        title = f"{movie.get('Title', '')} ({movie.get('Year', '')})"
        self.title_lbl.SetLabel(title)
        self.plot_txt.SetValue(movie.get("Plot", "No plot available"))

        poster_url = movie.get("Poster", "")
        if poster_url and poster_url != "N/A":
            try:
                resp = requests.get(poster_url, timeout=5)
                img_data = resp.content
                image = wx.Image(io.BytesIO(img_data))
                image = image.Scale(300, 400, wx.IMAGE_QUALITY_HIGH)
                bitmap = wx.Bitmap(image)
                self.poster_bitmap.SetBitmap(bitmap)
            except Exception:
                # no big deal if poster fails
                pass

        self.Layout()

    # ---------- WATCHLIST ----------

    def on_add_watchlist(self, event):
        if not self.current_movie:
            wx.MessageBox("Select a movie first", "Info", wx.OK | wx.ICON_INFORMATION)
            return

        imdb_id = self.current_movie.get("imdbID")
        if not imdb_id:
            wx.MessageBox("Cannot add this movie (missing imdbID)", "Error", wx.OK | wx.ICON_ERROR)
            return

        # store minimal info
        data = {
            "Title": self.current_movie.get("Title"),
            "Year": self.current_movie.get("Year"),
            "Type": self.current_movie.get("Type"),
            "imdbID": imdb_id,
        }

        try:
            self.auth_client.add_to_watchlist(imdb_id, data)
        except FirebaseAuthError as e:
            wx.MessageBox(str(e), "Watchlist Error", wx.OK | wx.ICON_ERROR)
            return

        wx.MessageBox("Added to watchlist", "Success", wx.OK | wx.ICON_INFORMATION)

    def on_show_watchlist(self, event):
        try:
            watchlist = self.auth_client.get_watchlist()
        except FirebaseAuthError as e:
            wx.MessageBox(str(e), "Watchlist Error", wx.OK | wx.ICON_ERROR)
            return

        if not watchlist:
            wx.MessageBox("Your watchlist is empty", "Watchlist", wx.OK | wx.ICON_INFORMATION)
            return

        items = []
        for imdb_id, movie in watchlist.items():
            items.append(f"{movie.get('Title', 'Unknown')} ({movie.get('Year', '')}) [{imdb_id}]")

        dlg = wx.MessageDialog(
            self,
            "\n".join(items),
            "Watchlist",
            style=wx.OK | wx.ICON_INFORMATION
        )
        dlg.ShowModal()
        dlg.Destroy()

    # ---------- AI INSIGHTS ----------

    def on_ai_insights(self, event):
        if not self.current_movie:
            wx.MessageBox("Select a movie first", "Info", wx.OK | wx.ICON_INFORMATION)
            return

        title = self.current_movie.get("Title", "Unknown")
        plot = self.current_movie.get("Plot", "")

        try:
            text = get_movie_insights(title, plot)
        except Exception as e:
            wx.MessageBox(str(e), "AI Error", wx.OK | wx.ICON_ERROR)
            return

        dlg = wx.Dialog(self, title=f"AI Insights – {title}", size=(600, 400))
        panel = wx.Panel(dlg)
        vbox = wx.BoxSizer(wx.VERTICAL)

        txt = wx.TextCtrl(panel, value=text, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_WORDWRAP)
        vbox.Add(txt, 1, wx.ALL | wx.EXPAND, 5)

        panel.SetSizer(vbox)
        dlg.Centre()
        dlg.ShowModal()
        dlg.Destroy()
