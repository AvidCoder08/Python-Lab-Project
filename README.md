# PythonLabProject app

## Run the app

### IMDb-like wxPython UI

This project also includes a desktop UI built with wxPython that looks similar to IMDb for searching and browsing movies using the OMDb API.

1) Install dependencies (wxPython and others):

```
pip install -r requirements.txt
```

2) (Optional) Configure your OMDb API key. Create a `.env` file in the project root or set an environment variable:

```
OMDB_API_KEY=your_api_key_here
```

If not provided, a demo key is used which may be rate-limited.

3) Run the wx app:

```
python imdb_wx.py
```

### uv

Run as a desktop app:

```
uv run flet run
```

Run as a web app:

```
uv run flet run --web
```

### Poetry

Install dependencies from `pyproject.toml`:

```
poetry install
```

Run as a desktop app:

```
poetry run flet run
```

Run as a web app:

```
poetry run flet run --web
```

For more details on running the app, refer to the [Getting Started Guide](https://flet.dev/docs/getting-started/).

## Build the app

### Android

```
flet build apk -v
```

For more details on building and signing `.apk` or `.aab`, refer to the [Android Packaging Guide](https://flet.dev/docs/publish/android/).

### iOS

```
flet build ipa -v
```

For more details on building and signing `.ipa`, refer to the [iOS Packaging Guide](https://flet.dev/docs/publish/ios/).

### macOS

```
flet build macos -v
```

For more details on building macOS package, refer to the [macOS Packaging Guide](https://flet.dev/docs/publish/macos/).

### Linux

```
flet build linux -v
```

For more details on building Linux package, refer to the [Linux Packaging Guide](https://flet.dev/docs/publish/linux/).

### Windows

```
flet build windows -v
```

For more details on building Windows package, refer to the [Windows Packaging Guide](https://flet.dev/docs/publish/windows/).