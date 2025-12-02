# main.py
import wx
from ui import LoginFrame


def main():
    app = wx.App(False)
    LoginFrame()
    app.MainLoop()


if __name__ == "__main__":
    main()
