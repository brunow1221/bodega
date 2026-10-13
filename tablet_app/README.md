# Consulta de bodega para tablet

Aplicación web instalable (PWA) de solo lectura para tablets Android. Muestra nombre, categoría, stock disponible, ubicación, formato/medidas y estado. La consulta no solicita precio, stock mínimo ni códigos del producto.

## Probar en este equipo

Desde PowerShell, en la carpeta principal del proyecto:

```powershell
.\tablet_app\iniciar_local.ps1
```

Luego abra `http://localhost:8080`.

## Crear el paquete para el NAS

Desde PowerShell, en la carpeta principal del proyecto:

```powershell
powershell -ExecutionPolicy Bypass -File ".\tablet_app\generar_paquete_nas.ps1"
```

El resultado queda en `dist/bodega-tablet-nas.zip`. El paquete contiene solamente
los archivos públicos necesarios para la vista de la tablet.

## Publicar en el NAS e instalar en Android

1. Cree en el servidor web del NAS una carpeta, por ejemplo `bodega`.
2. Descomprima dentro de ella el contenido de `bodega-tablet-nas.zip`.
3. Publique esa carpeta mediante **HTTPS con un certificado válido**. Una dirección
   típica sería `https://nas.empresa.cl/bodega/`.
4. Abra esa dirección en Chrome desde la tablet, pulse **Instalar** y confirme.

La instalación PWA completa no funciona desde una dirección HTTP del tipo
`http://192.168.x.x`. Para que aparezca el botón **Instalar**, Chrome exige HTTPS
y la tablet debe confiar en el certificado del NAS.

Cuando publique una actualización, genere nuevamente el ZIP y reemplace el
contenido de la carpeta web. La aplicación instalada descargará la versión nueva
al volver a abrirla.

## Publicar con Docker en el NAS

Genere un paquete Docker listo para subir:

```powershell
powershell -ExecutionPolicy Bypass -File ".\tablet_app\generar_paquete_docker.ps1"
```

Se generan `dist/bodega-tablet-docker.zip` y
`dist/bodega-tablet-docker.tar.gz`. Ambos incluyen un archivo `.env` que contiene
exclusivamente la URL y la clave pública de Supabase. Para un NAS sin `unzip`,
utilice el archivo `.tar.gz`.

En el NAS:

```bash
unzip bodega-tablet-docker.zip -d bodega-tablet
cd bodega-tablet
docker compose up -d --build
```

### Instalación completa mediante SSH

Desde PowerShell en el PC, cambie `USUARIO` e `IP-DEL-NAS`:

```powershell
scp ".\dist\bodega-tablet-docker.zip" USUARIO@IP-DEL-NAS:~/
ssh USUARIO@IP-DEL-NAS
```

Una vez conectado al NAS:

```bash
mkdir -p "$HOME/docker/bodega-tablet"
unzip -o "$HOME/bodega-tablet-docker.zip" -d "$HOME/docker/bodega-tablet"
cd "$HOME/docker/bodega-tablet"
sh instalar_nas.sh
```

Si el usuario no tiene permiso para controlar Docker, ejecute el último comando
como administrador:

```bash
sudo sh instalar_nas.sh
```

Si Tailscale está instalado en el NAS, el instalador también ejecutará Tailscale
Serve y mostrará una dirección privada HTTPS terminada en `.ts.net`. Esa es la
dirección que debe abrir en la tablet conectada a la misma red Tailscale. No use
la IP local ni la IP `100.x` para instalar la PWA.

Para revisar posteriormente la dirección publicada:

```bash
sudo tailscale serve status
```

La vista quedará disponible internamente en `http://IP-DEL-NAS:8080`. Configure
el proxy inverso del NAS para publicar ese destino mediante una dirección HTTPS.
Se recomienda usar un nombre dedicado como `https://bodega.empresa.cl/`, porque
así no es necesario reescribir rutas. En la tablet abra la dirección HTTPS con
Chrome y pulse **Instalar**.

Para actualizar el contenedor, reemplace los archivos por los de un paquete nuevo
y ejecute:

```bash
docker compose up -d --build
```

`config.js` contiene solamente la URL y la clave pública de Supabase y está excluido de Git. No use una clave `service_role`.

La política de lectura `003_politicas_lectura_app.sql` debe estar aplicada en Supabase para que la clave pública pueda consultar `productos` y `ubicaciones`. Las escrituras permanecen bloqueadas por las políticas existentes.
