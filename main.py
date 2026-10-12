from datetime import datetime
import sqlite3
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="API Sistema Agua Fortuna 💧")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_NAME = "agua_fortuna.db"


def init_db():
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()

  # Clientes
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            telefono TEXT NOT NULL,
            direccion TEXT,
            tipo_cliente TEXT DEFAULT 'Residencial',
            envases_prestados INTEGER DEFAULT 0
        )
    """)

  # Repartidores
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS repartidores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            telefono TEXT,
            zona TEXT
        )
    """)

  # Pedidos
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS pedidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER,
            repartidor_id INTEGER,
            fecha TEXT,
            botellones_entregados INTEGER,
            botellones_recogidos INTEGER,
            total_pagar REAL,
            monto_pagado REAL,
            estado_pago TEXT,
            estado_pedido TEXT DEFAULT 'Pendiente',
            FOREIGN KEY(cliente_id) REFERENCES clientes(id),
            FOREIGN KEY(repartidor_id) REFERENCES repartidores(id)
        )
    """)

  # Gastos
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS gastos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,
            categoria TEXT,
            descripcion TEXT,
            monto REAL
        )
    """)

  # Liquidaciones
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS liquidaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repartidor_id INTEGER,
            fecha TEXT,
            efectivo_entregado REAL,
            transferencias REAL,
            botellones_vendidos INTEGER,
            envases_recogidos INTEGER,
            observacion TEXT,
            FOREIGN KEY(repartidor_id) REFERENCES repartidores(id)
        )
    """)

  # Inventario Planta
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventario_planta (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item TEXT UNIQUE,
            stock INTEGER DEFAULT 0
        )
    """)
  cursor.execute(
      "INSERT OR IGNORE INTO inventario_planta (item, stock) VALUES ('Botellones"
      " Llenos', 50)"
  )
  cursor.execute(
      "INSERT OR IGNORE INTO inventario_planta (item, stock) VALUES"
      " ('Botellones Vacíos', 20)"
  )
  cursor.execute(
      "INSERT OR IGNORE INTO inventario_planta (item, stock) VALUES ('Galones"
      " 5L', 30)"
  )
  cursor.execute(
      "INSERT OR IGNORE INTO inventario_planta (item, stock) VALUES ('Botellas"
      " 625ml', 100)"
  )
  cursor.execute(
      "INSERT OR IGNORE INTO inventario_planta (item, stock) VALUES ('Tapas',"
      " 500)"
  )
  cursor.execute(
      "INSERT OR IGNORE INTO inventario_planta (item, stock) VALUES ('Sellos',"
      " 500)"
  )

  # Producción Planta
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS produccion (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,
            botellones_20l INTEGER DEFAULT 0,
            galones_5l INTEGER DEFAULT 0,
            botellas_625ml INTEGER DEFAULT 0,
            operador TEXT,
            observaciones TEXT
        )
    """)

  conn.commit()
  conn.close()


init_db()


# --- MODELOS PYDANTIC ---
class ClienteCreate(BaseModel):
  nombre: str
  telefono: str
  direccion: Optional[str] = ""


class PedidoCreate(BaseModel):
  cliente_id: int
  botellones_entregados: int
  botellones_recogidos: int
  precio_unitario: float
  monto_pagado: float


class GastoCreate(BaseModel):
  categoria: str
  descripcion: str
  monto: float


class RepartidorCreate(BaseModel):
  nombre: str
  telefono: str
  zona: str


class LiquidacionCreate(BaseModel):
  repartidor_id: int
  efectivo_entregado: float
  transferencias: float
  botellones_vendidos: int
  envases_recogidos: int
  observacion: Optional[str] = ""


class ProduccionCreate(BaseModel):
  botellones_20l: int
  galones_5l: int
  botellas_625ml: int
  operador: Optional[str] = "Planta Principal"
  observaciones: Optional[str] = ""


# --- RUTAS: CLIENTES ---
@app.get("/clientes")
def obtener_clientes():
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute(
      "SELECT id, nombre, telefono, direccion, envases_prestados FROM clientes"
  )
  filas = cursor.fetchall()
  conn.close()
  return [
      {
          "id": f[0],
          "nombre": f[1],
          "telefono": f[2],
          "direccion": f[3],
          "envases_prestados": f[4],
      }
      for f in filas
  ]


@app.post("/clientes")
def crear_cliente(cliente: ClienteCreate):
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute(
      "INSERT INTO clientes (nombre, telefono, direccion) VALUES (?, ?, ?)",
      (cliente.nombre, cliente.telefono, cliente.direccion),
  )
  conn.commit()
  cid = cursor.lastrowid
  conn.close()
  return {"id": cid, "mensaje": "Cliente creado exitosamente"}


# --- RUTAS: PEDIDOS ---
@app.post("/pedidos")
def crear_pedido(pedido: PedidoCreate):
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()

  cursor.execute(
      "SELECT nombre, telefono, envases_prestados FROM clientes WHERE id = ?",
      (pedido.cliente_id,),
  )
  cliente = cursor.fetchone()
  if not cliente:
    conn.close()
    raise HTTPException(status_code=404, detail="Cliente no encontrado")

  nombre_cliente, telefono_cliente, envases_actuales = cliente
  total = pedido.botellones_entregados * pedido.precio_unitario
  estado_pago = (
      "Pagado" if pedido.monto_pagado >= total else "Pendiente de Cobro"
  )
  fecha_hoy = datetime.now().strftime("%Y-%m-%d %H:%M")

  cursor.execute(
      """
        INSERT INTO pedidos (cliente_id, fecha, botellones_entregados, botellones_recogidos, total_pagar, monto_pagado, estado_pago)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
      (
          pedido.cliente_id,
          fecha_hoy,
          pedido.botellones_entregados,
          pedido.botellones_recogidos,
          total,
          pedido.monto_pagado,
          estado_pago,
      ),
  )

  nuevo_saldo = (
      envases_actuales + pedido.botellones_entregados - pedido.botellones_recogidos
  )
  cursor.execute(
      "UPDATE clientes SET envases_prestados = ? WHERE id = ?",
      (nuevo_saldo, pedido.cliente_id),
  )

  conn.commit()
  conn.close()

  return {
      "mensaje": "Pedido registrado",
      "total": total,
      "monto_pagado": pedido.monto_pagado,
      "nuevo_saldo_envases": nuevo_saldo,
      "cliente_nombre": nombre_cliente,
      "cliente_telefono": telefono_cliente,
  }


# --- RUTAS: GASTOS ---
@app.get("/gastos")
def obtener_gastos():
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute(
      "SELECT id, fecha, categoria, descripcion, monto FROM gastos ORDER BY id"
      " DESC"
  )
  filas = cursor.fetchall()
  conn.close()
  return [
      {
          "id": f[0],
          "fecha": f[1],
          "categoria": f[2],
          "descripcion": f[3],
          "monto": f[4],
      }
      for f in filas
  ]


@app.post("/gastos")
def crear_gasto(gasto: GastoCreate):
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  fecha_hoy = datetime.now().strftime("%Y-%m-%d %H:%M")
  cursor.execute(
      "INSERT INTO gastos (fecha, categoria, descripcion, monto) VALUES (?, ?,"
      " ?, ?)",
      (fecha_hoy, gasto.categoria, gasto.descripcion, gasto.monto),
  )
  conn.commit()
  gid = cursor.lastrowid
  conn.close()
  return {"id": gid, "mensaje": "Gasto registrado"}


# --- RUTAS: REPARTIDORES Y LIQUIDACIONES ---
@app.get("/repartidores")
def obtener_repartidores():
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute("SELECT id, nombre, telefono, zona FROM repartidores")
  filas = cursor.fetchall()
  conn.close()
  return [
      {"id": f[0], "nombre": f[1], "telefono": f[2], "zona": f[3]} for f in filas
  ]


@app.post("/repartidores")
def crear_repartidor(rep: RepartidorCreate):
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute(
      "INSERT INTO repartidores (nombre, telefono, zona) VALUES (?, ?, ?)",
      (rep.nombre, rep.telefono, rep.zona),
  )
  conn.commit()
  rid = cursor.lastrowid
  conn.close()
  return {"id": rid, "mensaje": "Repartidor registrado"}


@app.post("/liquidaciones")
def registrar_liquidacion(liq: LiquidacionCreate):
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  fecha_hoy = datetime.now().strftime("%Y-%m-%d %H:%M")
  cursor.execute(
      """
        INSERT INTO liquidaciones (repartidor_id, fecha, efectivo_entregado, transferencias, botellones_vendidos, envases_recogidos, observacion)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
      (
          liq.repartidor_id,
          fecha_hoy,
          liq.efectivo_entregado,
          liq.transferencias,
          liq.botellones_vendidos,
          liq.envases_recogidos,
          liq.observacion,
      ),
  )
  conn.commit()
  conn.close()
  return {"mensaje": "Liquidación guardada"}


# --- RUTAS: INVENTARIO Y ALERTAS ---
@app.get("/inventario")
def obtener_inventario():
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute("SELECT id, item, stock FROM inventario_planta")
  filas = cursor.fetchall()
  conn.close()
  return [{"id": f[0], "item": f[1], "stock": f[2]} for f in filas]


@app.post("/inventario/ajustar")
def ajustar_inventario(item_id: int, cantidad: int):
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute(
      "UPDATE inventario_planta SET stock = stock + ? WHERE id = ?",
      (cantidad, item_id),
  )
  conn.commit()
  conn.close()
  return {"mensaje": "Inventario actualizado"}


@app.get("/envases/alertas")
def alertas_envases():
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute(
      "SELECT id, nombre, telefono, envases_prestados FROM clientes WHERE"
      " envases_prestados >= 3 ORDER BY envases_prestados DESC"
  )
  filas = cursor.fetchall()
  conn.close()
  return [
      {
          "id": f[0],
          "nombre": f[1],
          "telefono": f[2],
          "envases_prestados": f[3],
      }
      for f in filas
  ]


# --- RUTAS: PRODUCCIÓN PLANTA ---
@app.get("/produccion")
def obtener_produccion():
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute(
      "SELECT id, fecha, botellones_20l, galones_5l, botellas_625ml, operador,"
      " observaciones FROM produccion ORDER BY id DESC"
  )
  filas = cursor.fetchall()
  conn.close()
  return [
      {
          "id": f[0],
          "fecha": f[1],
          "botellones_20l": f[2],
          "galones_5l": f[3],
          "botellas_625ml": f[4],
          "operador": f[5],
          "observaciones": f[6],
      }
      for f in filas
  ]


@app.post("/produccion")
def registrar_produccion(prod: ProduccionCreate):
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  fecha_hoy = datetime.now().strftime("%Y-%m-%d %H:%M")

  cursor.execute(
      """
        INSERT INTO produccion (fecha, botellones_20l, galones_5l, botellas_625ml, operador, observaciones)
        VALUES (?, ?, ?, ?, ?, ?)
    """,
      (
          fecha_hoy,
          prod.botellones_20l,
          prod.galones_5l,
          prod.botellas_625ml,
          prod.operador,
          prod.observaciones,
      ),
  )

  cursor.execute(
      "UPDATE inventario_planta SET stock = stock + ? WHERE item ="
      " 'Botellones Llenos'",
      (prod.botellones_20l,),
  )
  cursor.execute(
      "UPDATE inventario_planta SET stock = stock + ? WHERE item = 'Galones"
      " 5L'",
      (prod.galones_5l,),
  )
  cursor.execute(
      "UPDATE inventario_planta SET stock = stock + ? WHERE item = 'Botellas"
      " 625ml'",
      (prod.botellas_625ml,),
  )

  tapas_usadas = prod.botellones_20l + prod.galones_5l + prod.botellas_625ml
  cursor.execute(
      "UPDATE inventario_planta SET stock = stock - ? WHERE item = 'Tapas'",
      (tapas_usadas,),
  )

  conn.commit()
  conn.close()
  return {"mensaje": "Producción registrada y stock actualizado"}


# --- RUTAS: DASHBOARD ---
@app.get("/dashboard/resumen")
def resumen_dashboard():
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()

  cursor.execute("SELECT SUM(monto_pagado) FROM pedidos")
  total_ingresos = cursor.fetchone()[0] or 0.0

  cursor.execute("SELECT SUM(monto) FROM gastos")
  total_gastos = cursor.fetchone()[0] or 0.0

  cursor.execute("SELECT SUM(envases_prestados) FROM clientes")
  total_bidones_calle = cursor.fetchone()[0] or 0

  cursor.execute("SELECT COUNT(*) FROM clientes")
  total_clientes = cursor.fetchone()[0] or 0

  cursor.execute(
      "SELECT SUM(total_pagar - monto_pagado) FROM pedidos WHERE estado_pago ="
      " 'Pendiente de Cobro'"
  )
  total_por_cobrar = cursor.fetchone()[0] or 0.0

  conn.close()

  return {
      "total_ingresos": total_ingresos,
      "total_gastos": total_gastos,
      "ganancia_neta": total_ingresos - total_gastos,
      "total_bidones_calle": total_bidones_calle,
      "total_clientes": total_clientes,
      "total_por_cobrar": total_por_cobrar,
  }