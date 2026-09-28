"""Prueba de punta a punta en navegador real (Playwright).
Requisitos: pip install playwright && playwright install chromium
Uso: con el servidor levantado y datos demo cargados:
    BASE_URL=http://127.0.0.1:5000 python e2e/test_admin_flow.py
"""
import os
import asyncio, io
from PIL import Image
from playwright.async_api import async_playwright
B = os.getenv("BASE_URL", "http://127.0.0.1:5000")
SHOTS = os.getenv("SHOTS_DIR", "/tmp")
async def main():
    Image.new("RGB",(1000,800),(40,110,90)).save(f"{SHOTS}/up.png")
    async with async_playwright() as p:
        b=await p.chromium.launch(); ctx=await b.new_context(viewport={"width":1366,"height":900}, bypass_csp=True); pg=await ctx.new_page()
        errs=[]; pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: errs.append(m.text) if m.type=="error" and "fonts" not in m.text and "403" not in m.text else None)
        pg.on("dialog", lambda d: asyncio.ensure_future(d.accept()))
        await pg.goto(B+"/admin"); await pg.wait_for_timeout(1000)
        print("sin sesión redirige a:", pg.url)
        await pg.fill("#email","admin.demo@example.com"); await pg.fill("#password","AdminDemo123"); await pg.click("[data-login] button[type=submit]")
        await pg.wait_for_function("location.pathname.startsWith('/admin')", timeout=8000); await pg.wait_for_selector(".kpis")
        await pg.screenshot(path=f"{SHOTS}/a_dash.png")
        for path,sel in [("/admin/pedidos",".a-table"),("/admin/productos",".a-table"),("/admin/categorias",".a-table"),("/admin/usuarios",".a-table"),("/admin/fidelizacion","[data-settings]"),("/admin/promociones",".a-table"),("/admin/configuracion","[data-key=store]")]:
            await pg.click(f".a-nav a[href='{path}']"); await pg.wait_for_selector(sel); await pg.wait_for_timeout(300)
            await pg.screenshot(path=f"{SHOTS}/a_{path.split('/')[-1]}.png")
        # crear producto con imagen
        await pg.click(".a-nav a[href='/admin/productos']"); await pg.wait_for_selector(".a-table")
        await pg.click("text=Nuevo producto"); await pg.wait_for_selector("[data-product]")
        await pg.fill("#f-name","Producto real de prueba E2E"); import_sku = "E2E-" + __import__("uuid").uuid4().hex[:5]; await pg.fill("#f-sku", import_sku); await pg.fill("#f-price_cents","150.50"); await pg.fill("#f-stock","7")
        await pg.select_option("#f-status","active"); await pg.fill("#f-tags","nuevo, e2e")
        await pg.set_input_files("[data-upload]",f"{SHOTS}/up.png"); await pg.wait_for_selector(".a-images img")
        await pg.click("[data-product] button[type=submit]"); await pg.wait_for_timeout(1200)
        print("tras crear:", pg.url, await pg.text_content(".a-title"))
        await pg.screenshot(path=f"{SHOTS}/a_product_form.png", full_page=True)
        # pedido: cambiar estado
        await pg.click(".a-nav a[href='/admin/pedidos']"); await pg.wait_for_selector(".a-table a")
        await pg.click(".a-table tbody a >> nth=0"); await pg.wait_for_selector("[data-status]")
        await pg.click("[data-status] button[type=submit]"); await pg.wait_for_timeout(1000)
        print("estado:", await pg.text_content(".pill"))
        await pg.screenshot(path=f"{SHOTS}/a_order.png", full_page=True)
        # cupón
        await pg.click(".a-nav a[href='/admin/promociones']"); await pg.wait_for_selector("[data-new-c]")
        await pg.click("[data-new-c]"); await pg.fill("#f-code","verano25"); await pg.fill("#f-percent","25")
        await pg.click("[data-coupon] button[type=submit]"); await pg.wait_for_timeout(800)
        print("cupón creado:", await pg.locator("text=VERANO25").count())
        # config tienda + social inválida
        await pg.click(".a-nav a[href='/admin/configuracion']"); await pg.wait_for_selector("[data-key=social]")
        await pg.fill("[data-key=social] #f-instagram","javascript:alert(1)"); await pg.click("[data-key=social] button[type=submit]"); await pg.wait_for_timeout(600)
        print("error social:", await pg.locator("[data-key=social] .field-error").count())
        await pg.fill("[data-key=contact] #f-whatsapp","+502 5555 5555"); await pg.click("[data-key=contact] button[type=submit]"); await pg.wait_for_timeout(600)
        # producto visible en la tienda
        await pg.goto(B+"/buscar?q=real%20de%20prueba"); await pg.wait_for_selector(".product-card, .state--empty")
        print("en tienda:", await pg.locator(".product-card").count())
        # rol limitado: cliente no entra
        c2=await b.new_context(bypass_csp=True); p2=await c2.new_page()
        await p2.goto(B+"/iniciar-sesion"); await p2.fill("#email","cliente.demo@example.com"); await p2.fill("#password","ClienteDemo123"); await p2.click("[data-login] button[type=submit]"); await p2.wait_for_timeout(1000)
        await p2.goto(B+"/admin"); await p2.wait_for_timeout(1000); print("cliente en /admin:", await p2.text_content("h1"))
        m=await b.new_context(viewport={"width":390,"height":844}, storage_state=await ctx.storage_state()); mp=await m.new_page()
        await mp.goto(B+"/admin/productos"); await mp.wait_for_timeout(1200); await mp.screenshot(path=f"{SHOTS}/a_mobile.png")
        print("errores:", errs); await b.close()
asyncio.run(main())
