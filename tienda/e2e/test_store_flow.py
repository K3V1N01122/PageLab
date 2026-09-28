"""Prueba de punta a punta en navegador real (Playwright).
Requisitos: pip install playwright && playwright install chromium
Uso: con el servidor levantado y datos demo cargados:
    BASE_URL=http://127.0.0.1:5000 python e2e/test_store_flow.py
"""
import os
import asyncio, uuid
from playwright.async_api import async_playwright
B = os.getenv("BASE_URL", "http://127.0.0.1:5000")
SHOTS = os.getenv("SHOTS_DIR", "/tmp")
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={"width":1280,"height":900}, bypass_csp=True); pg = await ctx.new_page()
        errs=[]; pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append(m.text) if m.type=="error" and "fonts" not in m.text and "403" not in m.text else None)
        pg.on("dialog", lambda d: asyncio.ensure_future(d.accept()))
        # invitado agrega al carrito
        await pg.goto(B+"/producto/mochila-urbana-20-l-demo"); await pg.wait_for_selector("h1")
        await pg.click("[data-step='1']"); await pg.click("button[value=add]"); await pg.wait_for_timeout(700)
        print("contador invitado:", await pg.text_content(".cart-count"))
        await pg.goto(B+"/carrito"); await pg.wait_for_selector(".cart-line")
        print("carrito invitado total:", await pg.text_content(".totals__total dd"))
        # registro (fusiona carrito)
        email=f"e2e{uuid.uuid4().hex[:6]}@example.com"
        await pg.goto(B+"/registro?next=/checkout")
        for k,v in {"#first_name":"Prueba","#last_name":"E2E","#email":email,"#password":"Clave1234","#password_confirm":"Clave1234"}.items(): await pg.fill(k,v)
        await pg.check("[name=accept_terms]"); await pg.click("[data-register] button[type=submit]"); await pg.wait_for_timeout(1500); await pg.screenshot(path=f"{SHOTS}/e2e_reg.png")
        await pg.wait_for_function("location.pathname.startsWith('/checkout')", timeout=8000); await pg.wait_for_selector("[data-submit]")
        await pg.wait_for_timeout(800)
        print("checkout total:", await pg.text_content(".totals__total dd"))
        await pg.check("input[value=standard]"); await pg.wait_for_timeout(500)
        await pg.fill("#a-recipient","Prueba E2E"); await pg.fill("#a-phone","55555555"); await pg.fill("#a-line1","6a avenida 1-23 zona 1"); await pg.fill("#a-city","Guatemala")
        await pg.fill("#k-coupon","DEMO10"); await pg.click("[data-apply]"); await pg.wait_for_timeout(800)
        print("con cupón y envío:", await pg.text_content(".totals__total dd"))
        await pg.screenshot(path=f"{SHOTS}/e2e_checkout.png", full_page=True)
        await pg.click("[data-submit]"); await pg.wait_for_function("location.pathname.startsWith('/pedido/')", timeout=8000); await pg.wait_for_selector("h1")
        print("confirmación:", await pg.text_content(".page-lead"))
        await pg.screenshot(path=f"{SHOTS}/e2e_confirm.png")
        await pg.click("text=Ver detalle del pedido"); await pg.wait_for_selector(".timeline")
        await pg.screenshot(path=f"{SHOTS}/e2e_detail.png", full_page=True)
        # cliente demo: canje
        await pg.click("[data-logout]"); await pg.wait_for_timeout(700)
        await pg.goto(B+"/iniciar-sesion"); await pg.fill("#email","cliente.demo@example.com"); await pg.fill("#password","ClienteDemo123")
        await pg.click("[data-login] button[type=submit]"); await pg.wait_for_function("location.pathname.startsWith('/cuenta')", timeout=8000); await pg.wait_for_selector(".loyalty-card")
        await pg.screenshot(path=f"{SHOTS}/e2e_account.png")
        await pg.goto(B+"/recompensas"); await pg.wait_for_selector("[data-redeem]")
        await pg.click("[data-redeem]:not([disabled])"); await pg.wait_for_selector(".notice--success")
        print("canje:", (await pg.text_content(".notice--success")).strip()[:160])
        await pg.goto(B+"/cuenta/puntos"); await pg.wait_for_selector(".table")
        await pg.screenshot(path=f"{SHOTS}/e2e_points.png", full_page=True)
        # mobile carrito/checkout
        m = await b.new_context(viewport={"width":390,"height":844}, bypass_csp=True); mp = await m.new_page()
        await mp.goto(B+"/producto/gorra-clasica-demo"); await mp.wait_for_selector("h1"); await mp.click("button[value=add]"); await mp.wait_for_timeout(600)
        await mp.goto(B+"/carrito"); await mp.wait_for_selector(".cart-line"); await mp.screenshot(path=f"{SHOTS}/m_cart.png", full_page=True)
        await mp.goto(B+"/producto/gorra-clasica-demo"); await mp.wait_for_timeout(900); await mp.screenshot(path=f"{SHOTS}/m_product.png")
        await mp.click("[data-action=menu]"); await mp.screenshot(path=f"{SHOTS}/m_menu.png")
        print("errores de consola:", errs)
        await b.close()
asyncio.run(main())
