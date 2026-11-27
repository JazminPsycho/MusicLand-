"""Run the real browser workflow against an isolated Waitress installation."""
import argparse
import contextlib
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
WIDTHS = (360, 390, 768, 1280)


@contextlib.contextmanager
def server():
    with tempfile.TemporaryDirectory(prefix="japs-browser-") as data:
        code = """
from server import create_app
from waitress import create_server
app = create_app()
httpd = create_server(app, host='127.0.0.1', port=0)
print(httpd.effective_port, app.config['SETUP_TOKEN'], flush=True)
httpd.run()
"""
        process = subprocess.Popen(
            [str(ROOT / ".venv/bin/python"), "-c", code],
            cwd=ROOT, env={**os.environ, "JAPS_DATA": data},
            stdout=subprocess.PIPE, text=True,
        )
        try:
            port, token = process.stdout.readline().split()
            yield f"http://127.0.0.1:{port}", token
        finally:
            process.terminate()
            process.wait(timeout=10)


def wait_for_media(page, condition):
    for _ in range(100):
        if page.locator("audio").evaluate(condition):
            return
        time.sleep(.05)
    raise AssertionError(page.locator("audio").evaluate("(a) => ({paused:a.paused,time:a.currentTime,error:a.error?.message})"))


def layout(page, width):
    assert page.evaluate("document.documentElement.scrollWidth") <= width
    assert page.locator("#player button:not([disabled]), #seek").evaluate_all(
        "controls => controls.every(c => c.offsetHeight >= 44 && c.offsetWidth >= 44)"
    )
    page.locator("footer").evaluate("element => element.scrollIntoView({block:'end'})")
    assert page.locator("footer").bounding_box()["y"] + page.locator("footer").bounding_box()["height"] <= page.locator("#player").bounding_box()["y"]


def check(browser, width, engine, screenshot):
    with server() as (url, token):
        ctx = browser.new_context(viewport={"width": width, "height": 800})
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(url)
        page.get_by_label("Nombre de usuario").fill("pruebas")
        page.get_by_label("Contraseña").fill("disposable-password")
        page.get_by_label("Token local").fill(token)
        page.get_by_role("button", name="Crear administradora").click()
        page.get_by_role("button", name="Importar álbum").click()
        expect(page.get_by_role("textbox", name="Álbum", exact=True)).to_be_focused()
        page.get_by_role("textbox", name="Álbum", exact=True).fill("Última luz")
        page.get_by_role("textbox", name="Artista", exact=True).fill("Muestras JAPs")
        wavs = sorted((ROOT / "example").glob("*.wav"))[:2]
        page.get_by_label("Agregar pistas WAV PCM").set_input_files(wavs)
        page.get_by_role("textbox", name="Pista 1", exact=True).fill("Primera señal")
        page.get_by_role("textbox", name="Pista 2", exact=True).fill("Segunda señal")
        page.get_by_role("button", name="Bajar pista 1").press("Enter")
        expect(page.get_by_role("textbox", name="Pista 2", exact=True)).to_be_focused()
        page.get_by_role("button", name="Subir pista 2").press("Enter")
        expect(page.get_by_role("textbox", name="Pista 1", exact=True)).to_be_focused()
        assert page.evaluate("document.documentElement.scrollWidth") <= width

        second_upload = "**/api/imports/*/files/1"
        page.route(second_upload, lambda route: route.abort())
        page.get_by_role("button", name="Preparar álbum").click()
        expect(page.locator("#notice")).to_contain_text("las pistas recibidas se conservan")
        expect(page.get_by_text("Recibida · 0:12")).to_be_visible()
        page.reload()
        page.get_by_role("button", name="Importar", exact=True).click()
        expect(page.get_by_text("Recibida · 0:12")).to_be_visible()
        expect(page.get_by_role("textbox", name="Pista 2", exact=True)).to_have_value("Segunda señal")
        page.unroute(second_upload)
        uploaded = []
        page.on("request", lambda req: uploaded.append(req.url) if req.method == "PUT" and "/files/" in req.url else None)
        page.get_by_label("Seleccionar este WAV").set_input_files(wavs[1])
        page.get_by_role("button", name="Preparar álbum").click()
        expect(page.get_by_role("button", name="Abrir álbum")).to_be_visible(timeout=12000)
        assert [u.rsplit("/", 1)[1] for u in uploaded] == ["1"], uploaded

        page.get_by_role("button", name="Biblioteca", exact=True).click()
        search = page.get_by_role("searchbox", name="Buscar en la biblioteca")
        expect(search).to_be_focused()
        search.fill("ausente")
        expect(page.get_by_text("Sin coincidencias")).to_be_visible()
        search.fill("primera senal")
        page.keyboard.press("Tab")
        page.keyboard.press("Tab")
        expect(page.locator(".album")).to_be_focused()
        page.keyboard.press("Enter")
        expect(page.get_by_role("heading", name="Última luz")).to_be_focused()
        page.get_by_role("button", name=re.compile("Primera señal")).click()
        wait_for_media(page, "a => !a.paused && a.currentTime > .1")
        page.get_by_role("button", name="Pausar").click()
        wait_for_media(page, "a => a.paused")
        seek = page.get_by_role("slider", name="Posición de reproducción")
        box = seek.bounding_box()
        seek.click(position={"x": box["width"] * .8, "y": box["height"] / 2})
        seek.press("ArrowLeft")
        wait_for_media(page, "a => a.currentTime > 8")
        page.get_by_role("button", name="Pista siguiente").click()
        expect(page.locator("#now")).to_have_text("Segunda señal")
        expect(page.locator("#artist")).to_have_text("Muestras JAPs")
        wait_for_media(page, "a => !a.paused && a.currentTime > .1")
        page.get_by_role("button", name="Pausar").click()
        page.get_by_role("button", name="← Biblioteca").click()
        expect(search).to_have_value("primera senal")
        expect(page.locator("#player")).to_be_visible()
        layout(page, width)
        if screenshot:
            page.evaluate("window.scrollTo(0,0)")
            page.screenshot(path=screenshot / f"{engine}-{width}.png")
        assert not errors, errors
        ctx.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("engine", choices=["chromium", "webkit"])
    parser.add_argument("--width", type=int, choices=WIDTHS)
    parser.add_argument("--screenshots", type=Path)
    args = parser.parse_args()
    if args.screenshots:
        args.screenshots.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        options = {}
        executable = os.environ.get("JAPS_" + args.engine.upper())
        if executable:
            options["executable_path"] = executable
        browser = getattr(playwright, args.engine).launch(**options)
        for width in (args.width,) if args.width else WIDTHS:
            check(browser, width, args.engine, args.screenshots)
            print(f"{args.engine} {browser.version} · {width}px · OK", flush=True)
        browser.close()


if __name__ == "__main__":
    main()
