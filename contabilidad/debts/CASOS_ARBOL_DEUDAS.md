# Árbol de casos — Deudas y pagos

Generado por `contabilidad/debts/casos_arbol.py`. **No editar a mano.**

`debe` = te deben (+) · `debo` = tú debes (−) · los pagos abonan el lado que les toca y lo que sobra queda como saldo a favor de quien pagó.

| Etiqueta | Qué agrega ese nivel |
|---|---|
| **S** | deuda sobrante |
| **I** | deuda igual |
| **N** | deuda insuficiente |
| **M** | deuda al lado mayor |
| **X** | agrego un debe |
| **Y** | agrego un debo |
| **E** | me pagan justo |
| **F** | me pagan de menos |
| **G** | me pagan de más |
| **P** | pago justo |
| **Q** | pago de menos |
| **R** | pago de más |

Cortes: profundidad máxima **nivel 4**, y una rama no se expande cuando su etiqueta repite la del padre (queda como hoja).

Cada caso cierra con un **cruce de cuentas** sobre lo que quedó pendiente después de los pagos: se compensa `min(pendiente debe, pendiente debo)` emparejando de la más antigua a la más reciente.

## Conteo

| Nivel | Casos |
|---|---|
| 1 | 4 |
| 2 | 14 |
| 3 | 108 |
| 4 | 796 |
| **Total** | **922** |

## Nivel 1

| ID | Caso | pend. debe | pend. debo | neto | cruzado | saldo final | quedan | hoja |
|---|---|---:|---:|---:|---:|---:|---|---|
| `A` | debe 100 | 100 | 0 | **+100** | 0 | +100 (te deben) | n1 100 |  |
| `A0` | debe 0 | 0 | 0 | **+0** | 0 | +0 (al día) | — | monto-0 |
| `B` | debo 100 | 0 | 100 | **-100** | 0 | -100 (tú debes) | n1 100 |  |
| `B0` | debo 0 | 0 | 0 | **+0** | 0 | +0 (al día) | — | monto-0 |

## Nivel 2

| ID | Caso | pend. debe | pend. debo | neto | cruzado | saldo final | quedan | hoja |
|---|---|---:|---:|---:|---:|---:|---|---|
| `AE` | debe 100 → E recibido 100 | 0 | 0 | **+0** | 0 | +0 (al día) | — |  |
| `AF` | debe 100 → F recibido 60 | 40 | 0 | **+40** | 0 | +40 (te deben) | n1 40⅟ |  |
| `AG` | debe 100 → G recibido 150 | 0 | 0 | **-50** | 0 | -50 (tú debes) |  · a favor deudor 50 |  |
| `AI` | debe 100 → I debo 100 | 100 | 100 | **+0** | 100 | +0 (al día) | — |  |
| `AN` | debe 100 → N debo 60 | 100 | 60 | **+40** | 60 | +40 (te deben) | n1 40⅟ |  |
| `AR` | debe 100 → R doy 50 | 100 | 0 | **+150** | 0 | +150 (te deben) | n1 100 · a favor tuyo 50 |  |
| `AS` | debe 100 → S debo 150 | 100 | 150 | **-50** | 100 | -50 (tú debes) | n2 50⅟ |  |
| `BG` | debo 100 → G recibido 50 | 0 | 100 | **-150** | 0 | -150 (tú debes) | n1 100 · a favor deudor 50 |  |
| `BI` | debo 100 → I debe 100 | 100 | 100 | **+0** | 100 | +0 (al día) | — |  |
| `BN` | debo 100 → N debe 60 | 60 | 100 | **-40** | 60 | -40 (tú debes) | n1 40⅟ |  |
| `BP` | debo 100 → P doy 100 | 0 | 0 | **+0** | 0 | +0 (al día) | — |  |
| `BQ` | debo 100 → Q doy 60 | 0 | 40 | **-40** | 0 | -40 (tú debes) | n1 40⅟ |  |
| `BR` | debo 100 → R doy 150 | 0 | 0 | **+50** | 0 | +50 (te deben) |  · a favor tuyo 50 |  |
| `BS` | debo 100 → S debe 150 | 150 | 100 | **+50** | 100 | +50 (te deben) | n2 50⅟ |  |

## Nivel 3

| ID | Caso | pend. debe | pend. debo | neto | cruzado | saldo final | quedan | hoja |
|---|---|---:|---:|---:|---:|---:|---|---|
| `AEG` | debe 100 → E recibido 100 → G recibido 50 | 0 | 0 | **-50** | 0 | -50 (tú debes) |  · a favor deudor 50 |  |
| `AER` | debe 100 → E recibido 100 → R doy 50 | 0 | 0 | **+50** | 0 | +50 (te deben) |  · a favor tuyo 50 |  |
| `AEX` | debe 100 → E recibido 100 → X debe 50 | 50 | 0 | **+50** | 0 | +50 (te deben) | n3 50 |  |
| `AEY` | debe 100 → E recibido 100 → Y debo 50 | 0 | 50 | **-50** | 0 | -50 (tú debes) | n3 50 |  |
| `AFE` | debe 100 → F recibido 60 → E recibido 40 | 0 | 0 | **+0** | 0 | +0 (al día) | — |  |
| `AFF` | debe 100 → F recibido 60 → F recibido 20 | 20 | 0 | **+20** | 0 | +20 (te deben) | n1 20⅟ | repetido |
| `AFG` | debe 100 → F recibido 60 → G recibido 60 | 0 | 0 | **-20** | 0 | -20 (tú debes) |  · a favor deudor 20 |  |
| `AFI` | debe 100 → F recibido 60 → I debo 40 | 40 | 40 | **+0** | 40 | +0 (al día) | — |  |
| `AFM` | debe 100 → F recibido 60 → M debe 50 | 90 | 0 | **+90** | 0 | +90 (te deben) | n1 40⅟, n3 50 |  |
| `AFN` | debe 100 → F recibido 60 → N debo 20 | 40 | 20 | **+20** | 20 | +20 (te deben) | n1 20⅟ |  |
| `AFR` | debe 100 → F recibido 60 → R doy 50 | 40 | 0 | **+90** | 0 | +90 (te deben) | n1 40⅟ · a favor tuyo 50 |  |
| `AFS` | debe 100 → F recibido 60 → S debo 60 | 40 | 60 | **-20** | 40 | -20 (tú debes) | n3 20⅟ |  |
| `AGG` | debe 100 → G recibido 150 → G recibido 50 | 0 | 0 | **-100** | 0 | -100 (tú debes) |  · a favor deudor 100 | repetido |
| `AGI` | debe 100 → G recibido 150 → I debe 50 | 0 | 0 | **+0** | 0 | +0 (al día) | — |  |
| `AGM` | debe 100 → G recibido 150 → M debo 60 | 0 | 60 | **-110** | 0 | -110 (tú debes) | n3 60 · a favor deudor 50 |  |
| `AGN` | debe 100 → G recibido 150 → N debe 30 | 0 | 0 | **-20** | 0 | -20 (tú debes) |  · a favor deudor 20 |  |
| `AGR` | debe 100 → G recibido 150 → R doy 50 | 0 | 0 | **+0** | 0 | +0 (al día) |  · a favor deudor 50 · a favor tuyo 50 |  |
| `AGS` | debe 100 → G recibido 150 → S debe 75 | 25 | 0 | **+25** | 0 | +25 (te deben) | n3 25⅟ |  |
| `AIE` | debe 100 → I debo 100 → E recibido 100 | 0 | 100 | **-100** | 0 | -100 (tú debes) | n2 100 |  |
| `AIF` | debe 100 → I debo 100 → F recibido 60 | 40 | 100 | **-60** | 40 | -60 (tú debes) | n2 60⅟ |  |
| `AIG` | debe 100 → I debo 100 → G recibido 150 | 0 | 100 | **-150** | 0 | -150 (tú debes) | n2 100 · a favor deudor 50 |  |
| `AIP` | debe 100 → I debo 100 → P doy 100 | 100 | 0 | **+100** | 0 | +100 (te deben) | n1 100 |  |
| `AIQ` | debe 100 → I debo 100 → Q doy 60 | 100 | 40 | **+60** | 40 | +60 (te deben) | n1 60⅟ |  |
| `AIR` | debe 100 → I debo 100 → R doy 150 | 100 | 0 | **+150** | 0 | +150 (te deben) | n1 100 · a favor tuyo 50 |  |
| `AIX` | debe 100 → I debo 100 → X debe 50 | 150 | 100 | **+50** | 100 | +50 (te deben) | n3 50 |  |
| `AIY` | debe 100 → I debo 100 → Y debo 50 | 100 | 150 | **-50** | 100 | -50 (tú debes) | n3 50 |  |
| `ANE` | debe 100 → N debo 60 → E recibido 100 | 0 | 60 | **-60** | 0 | -60 (tú debes) | n2 60 |  |
| `ANF` | debe 100 → N debo 60 → F recibido 60 | 40 | 60 | **-20** | 40 | -20 (tú debes) | n2 20⅟ |  |
| `ANG` | debe 100 → N debo 60 → G recibido 150 | 0 | 60 | **-110** | 0 | -110 (tú debes) | n2 60 · a favor deudor 50 |  |
| `ANI` | debe 100 → N debo 60 → I debo 40 | 100 | 100 | **+0** | 100 | +0 (al día) | — |  |
| `ANM` | debe 100 → N debo 60 → M debe 50 | 150 | 60 | **+90** | 60 | +90 (te deben) | n1 40⅟, n3 50 |  |
| `ANN` | debe 100 → N debo 60 → N debo 20 | 100 | 80 | **+20** | 80 | +20 (te deben) | n1 20⅟ | repetido |
| `ANP` | debe 100 → N debo 60 → P doy 60 | 100 | 0 | **+100** | 0 | +100 (te deben) | n1 100 |  |
| `ANQ` | debe 100 → N debo 60 → Q doy 35 | 100 | 25 | **+75** | 25 | +75 (te deben) | n1 75⅟ |  |
| `ANR` | debe 100 → N debo 60 → R doy 90 | 100 | 0 | **+130** | 0 | +130 (te deben) | n1 100 · a favor tuyo 30 |  |
| `ANS` | debe 100 → N debo 60 → S debo 60 | 100 | 120 | **-20** | 100 | -20 (tú debes) | n3 20⅟ |  |
| `ARE` | debe 100 → R doy 50 → E recibido 100 | 0 | 0 | **+50** | 0 | +50 (te deben) |  · a favor tuyo 50 |  |
| `ARF` | debe 100 → R doy 50 → F recibido 60 | 40 | 0 | **+90** | 0 | +90 (te deben) | n1 40⅟ · a favor tuyo 50 |  |
| `ARG` | debe 100 → R doy 50 → G recibido 150 | 0 | 0 | **+0** | 0 | +0 (al día) |  · a favor deudor 50 · a favor tuyo 50 |  |
| `ARI` | debe 100 → R doy 50 → I debo 150 | 100 | 100 | **+0** | 100 | +0 (al día) | — |  |
| `ARM` | debe 100 → R doy 50 → M debe 190 | 290 | 0 | **+340** | 0 | +340 (te deben) | n1 100, n3 190 · a favor tuyo 50 |  |
| `ARN` | debe 100 → R doy 50 → N debo 90 | 100 | 40 | **+60** | 40 | +60 (te deben) | n1 60⅟ |  |
| `ARR` | debe 100 → R doy 50 → R doy 50 | 100 | 0 | **+200** | 0 | +200 (te deben) | n1 100 · a favor tuyo 100 | repetido |
| `ARS` | debe 100 → R doy 50 → S debo 225 | 100 | 175 | **-75** | 100 | -75 (tú debes) | n3 75⅟ |  |
| `ASE` | debe 100 → S debo 150 → E recibido 100 | 0 | 150 | **-150** | 0 | -150 (tú debes) | n2 150 |  |
| `ASF` | debe 100 → S debo 150 → F recibido 60 | 40 | 150 | **-110** | 40 | -110 (tú debes) | n2 110⅟ |  |
| `ASG` | debe 100 → S debo 150 → G recibido 150 | 0 | 150 | **-200** | 0 | -200 (tú debes) | n2 150 · a favor deudor 50 |  |
| `ASI` | debe 100 → S debo 150 → I debe 50 | 150 | 150 | **+0** | 150 | +0 (al día) | — |  |
| `ASM` | debe 100 → S debo 150 → M debo 60 | 100 | 210 | **-110** | 100 | -110 (tú debes) | n2 50⅟, n3 60 |  |
| `ASN` | debe 100 → S debo 150 → N debe 30 | 130 | 150 | **-20** | 130 | -20 (tú debes) | n2 20⅟ |  |
| `ASP` | debe 100 → S debo 150 → P doy 150 | 100 | 0 | **+100** | 0 | +100 (te deben) | n1 100 |  |
| `ASQ` | debe 100 → S debo 150 → Q doy 90 | 100 | 60 | **+40** | 60 | +40 (te deben) | n1 40⅟ |  |
| `ASR` | debe 100 → S debo 150 → R doy 225 | 100 | 0 | **+175** | 0 | +175 (te deben) | n1 100 · a favor tuyo 75 |  |
| `ASS` | debe 100 → S debo 150 → S debe 75 | 175 | 150 | **+25** | 150 | +25 (te deben) | n3 25⅟ | repetido |
| `BGG` | debo 100 → G recibido 50 → G recibido 50 | 0 | 100 | **-200** | 0 | -200 (tú debes) | n1 100 · a favor deudor 100 | repetido |
| `BGI` | debo 100 → G recibido 50 → I debe 150 | 100 | 100 | **+0** | 100 | +0 (al día) | — |  |
| `BGM` | debo 100 → G recibido 50 → M debo 190 | 0 | 290 | **-340** | 0 | -340 (tú debes) | n1 100, n3 190 · a favor deudor 50 |  |
| `BGN` | debo 100 → G recibido 50 → N debe 90 | 40 | 100 | **-60** | 40 | -60 (tú debes) | n1 60⅟ |  |
| `BGP` | debo 100 → G recibido 50 → P doy 100 | 0 | 0 | **-50** | 0 | -50 (tú debes) |  · a favor deudor 50 |  |
| `BGQ` | debo 100 → G recibido 50 → Q doy 60 | 0 | 40 | **-90** | 0 | -90 (tú debes) | n1 40⅟ · a favor deudor 50 |  |
| `BGR` | debo 100 → G recibido 50 → R doy 150 | 0 | 0 | **+0** | 0 | +0 (al día) |  · a favor deudor 50 · a favor tuyo 50 |  |
| `BGS` | debo 100 → G recibido 50 → S debe 225 | 175 | 100 | **+75** | 100 | +75 (te deben) | n3 75⅟ |  |
| `BIE` | debo 100 → I debe 100 → E recibido 100 | 0 | 100 | **-100** | 0 | -100 (tú debes) | n1 100 |  |
| `BIF` | debo 100 → I debe 100 → F recibido 60 | 40 | 100 | **-60** | 40 | -60 (tú debes) | n1 60⅟ |  |
| `BIG` | debo 100 → I debe 100 → G recibido 150 | 0 | 100 | **-150** | 0 | -150 (tú debes) | n1 100 · a favor deudor 50 |  |
| `BIP` | debo 100 → I debe 100 → P doy 100 | 100 | 0 | **+100** | 0 | +100 (te deben) | n2 100 |  |
| `BIQ` | debo 100 → I debe 100 → Q doy 60 | 100 | 40 | **+60** | 40 | +60 (te deben) | n2 60⅟ |  |
| `BIR` | debo 100 → I debe 100 → R doy 150 | 100 | 0 | **+150** | 0 | +150 (te deben) | n2 100 · a favor tuyo 50 |  |
| `BIX` | debo 100 → I debe 100 → X debe 50 | 150 | 100 | **+50** | 100 | +50 (te deben) | n3 50 |  |
| `BIY` | debo 100 → I debe 100 → Y debo 50 | 100 | 150 | **-50** | 100 | -50 (tú debes) | n3 50 |  |
| `BNE` | debo 100 → N debe 60 → E recibido 60 | 0 | 100 | **-100** | 0 | -100 (tú debes) | n1 100 |  |
| `BNF` | debo 100 → N debe 60 → F recibido 35 | 25 | 100 | **-75** | 25 | -75 (tú debes) | n1 75⅟ |  |
| `BNG` | debo 100 → N debe 60 → G recibido 90 | 0 | 100 | **-130** | 0 | -130 (tú debes) | n1 100 · a favor deudor 30 |  |
| `BNI` | debo 100 → N debe 60 → I debe 40 | 100 | 100 | **+0** | 100 | +0 (al día) | — |  |
| `BNM` | debo 100 → N debe 60 → M debo 50 | 60 | 150 | **-90** | 60 | -90 (tú debes) | n1 40⅟, n3 50 |  |
| `BNN` | debo 100 → N debe 60 → N debe 20 | 80 | 100 | **-20** | 80 | -20 (tú debes) | n1 20⅟ | repetido |
| `BNP` | debo 100 → N debe 60 → P doy 100 | 60 | 0 | **+60** | 0 | +60 (te deben) | n2 60 |  |
| `BNQ` | debo 100 → N debe 60 → Q doy 60 | 60 | 40 | **+20** | 40 | +20 (te deben) | n2 20⅟ |  |
| `BNR` | debo 100 → N debe 60 → R doy 150 | 60 | 0 | **+110** | 0 | +110 (te deben) | n2 60 · a favor tuyo 50 |  |
| `BNS` | debo 100 → N debe 60 → S debe 60 | 120 | 100 | **+20** | 100 | +20 (te deben) | n3 20⅟ |  |
| `BPG` | debo 100 → P doy 100 → G recibido 50 | 0 | 0 | **-50** | 0 | -50 (tú debes) |  · a favor deudor 50 |  |
| `BPR` | debo 100 → P doy 100 → R doy 50 | 0 | 0 | **+50** | 0 | +50 (te deben) |  · a favor tuyo 50 |  |
| `BPX` | debo 100 → P doy 100 → X debe 50 | 50 | 0 | **+50** | 0 | +50 (te deben) | n3 50 |  |
| `BPY` | debo 100 → P doy 100 → Y debo 50 | 0 | 50 | **-50** | 0 | -50 (tú debes) | n3 50 |  |
| `BQG` | debo 100 → Q doy 60 → G recibido 50 | 0 | 40 | **-90** | 0 | -90 (tú debes) | n1 40⅟ · a favor deudor 50 |  |
| `BQI` | debo 100 → Q doy 60 → I debe 40 | 40 | 40 | **+0** | 40 | +0 (al día) | — |  |
| `BQM` | debo 100 → Q doy 60 → M debo 50 | 0 | 90 | **-90** | 0 | -90 (tú debes) | n1 40⅟, n3 50 |  |
| `BQN` | debo 100 → Q doy 60 → N debe 20 | 20 | 40 | **-20** | 20 | -20 (tú debes) | n1 20⅟ |  |
| `BQP` | debo 100 → Q doy 60 → P doy 40 | 0 | 0 | **+0** | 0 | +0 (al día) | — |  |
| `BQQ` | debo 100 → Q doy 60 → Q doy 20 | 0 | 20 | **-20** | 0 | -20 (tú debes) | n1 20⅟ | repetido |
| `BQR` | debo 100 → Q doy 60 → R doy 60 | 0 | 0 | **+20** | 0 | +20 (te deben) |  · a favor tuyo 20 |  |
| `BQS` | debo 100 → Q doy 60 → S debe 60 | 60 | 40 | **+20** | 40 | +20 (te deben) | n3 20⅟ |  |
| `BRG` | debo 100 → R doy 150 → G recibido 50 | 0 | 0 | **+0** | 0 | +0 (al día) |  · a favor deudor 50 · a favor tuyo 50 |  |
| `BRI` | debo 100 → R doy 150 → I debo 50 | 0 | 0 | **+0** | 0 | +0 (al día) | — |  |
| `BRM` | debo 100 → R doy 150 → M debe 60 | 60 | 0 | **+110** | 0 | +110 (te deben) | n3 60 · a favor tuyo 50 |  |
| `BRN` | debo 100 → R doy 150 → N debo 30 | 0 | 0 | **+20** | 0 | +20 (te deben) |  · a favor tuyo 20 |  |
| `BRR` | debo 100 → R doy 150 → R doy 50 | 0 | 0 | **+100** | 0 | +100 (te deben) |  · a favor tuyo 100 | repetido |
| `BRS` | debo 100 → R doy 150 → S debo 75 | 0 | 25 | **-25** | 0 | -25 (tú debes) | n3 25⅟ |  |
| `BSE` | debo 100 → S debe 150 → E recibido 150 | 0 | 100 | **-100** | 0 | -100 (tú debes) | n1 100 |  |
| `BSF` | debo 100 → S debe 150 → F recibido 90 | 60 | 100 | **-40** | 60 | -40 (tú debes) | n1 40⅟ |  |
| `BSG` | debo 100 → S debe 150 → G recibido 225 | 0 | 100 | **-175** | 0 | -175 (tú debes) | n1 100 · a favor deudor 75 |  |
| `BSI` | debo 100 → S debe 150 → I debo 50 | 150 | 150 | **+0** | 150 | +0 (al día) | — |  |
| `BSM` | debo 100 → S debe 150 → M debe 60 | 210 | 100 | **+110** | 100 | +110 (te deben) | n2 50⅟, n3 60 |  |
| `BSN` | debo 100 → S debe 150 → N debo 30 | 150 | 130 | **+20** | 130 | +20 (te deben) | n2 20⅟ |  |
| `BSP` | debo 100 → S debe 150 → P doy 100 | 150 | 0 | **+150** | 0 | +150 (te deben) | n2 150 |  |
| `BSQ` | debo 100 → S debe 150 → Q doy 60 | 150 | 40 | **+110** | 40 | +110 (te deben) | n2 110⅟ |  |
| `BSR` | debo 100 → S debe 150 → R doy 150 | 150 | 0 | **+200** | 0 | +200 (te deben) | n2 150 · a favor tuyo 50 |  |
| `BSS` | debo 100 → S debe 150 → S debo 75 | 150 | 175 | **-25** | 150 | -25 (tú debes) | n3 25⅟ | repetido |

## Nivel 4

| ID | Caso | pend. debe | pend. debo | neto | cruzado | saldo final | quedan | hoja |
|---|---|---:|---:|---:|---:|---:|---|---|
| `AEGG` | debe 100 → E recibido 100 → G recibido 50 → G recibido 50 | 0 | 0 | **-100** | 0 | -100 (tú debes) |  · a favor deudor 100 | nivel-max |
| `AEGI` | debe 100 → E recibido 100 → G recibido 50 → I debe 50 | 0 | 0 | **+0** | 0 | +0 (al día) | — | nivel-max |
| `AEGM` | debe 100 → E recibido 100 → G recibido 50 → M debo 60 | 0 | 60 | **-110** | 0 | -110 (tú debes) | n4 60 · a favor deudor 50 | nivel-max |
| `AEGN` | debe 100 → E recibido 100 → G recibido 50 → N debe 30 | 0 | 0 | **-20** | 0 | -20 (tú debes) |  · a favor deudor 20 | nivel-max |
| `AEGR` | debe 100 → E recibido 100 → G recibido 50 → R doy 50 | 0 | 0 | **+0** | 0 | +0 (al día) |  · a favor deudor 50 · a favor tuyo 50 | nivel-max |
| `AEGS` | debe 100 → E recibido 100 → G recibido 50 → S debe 75 | 25 | 0 | **+25** | 0 | +25 (te deben) | n4 25⅟ | nivel-max |
| `AERG` | debe 100 → E recibido 100 → R doy 50 → G recibido 50 | 0 | 0 | **+0** | 0 | +0 (al día) |  · a favor deudor 50 · a favor tuyo 50 | nivel-max |
| `AERI` | debe 100 → E recibido 100 → R doy 50 → I debo 50 | 0 | 0 | **+0** | 0 | +0 (al día) | — | nivel-max |
| `AERM` | debe 100 → E recibido 100 → R doy 50 → M debe 60 | 60 | 0 | **+110** | 0 | +110 (te deben) | n4 60 · a favor tuyo 50 | nivel-max |
| `AERN` | debe 100 → E recibido 100 → R doy 50 → N debo 30 | 0 | 0 | **+20** | 0 | +20 (te deben) |  · a favor tuyo 20 | nivel-max |
| `AERR` | debe 100 → E recibido 100 → R doy 50 → R doy 50 | 0 | 0 | **+100** | 0 | +100 (te deben) |  · a favor tuyo 100 | nivel-max |
| `AERS` | debe 100 → E recibido 100 → R doy 50 → S debo 75 | 0 | 25 | **-25** | 0 | -25 (tú debes) | n4 25⅟ | nivel-max |
| `AEXE` | debe 100 → E recibido 100 → X debe 50 → E recibido 50 | 0 | 0 | **+0** | 0 | +0 (al día) | — | nivel-max |
| `AEXF` | debe 100 → E recibido 100 → X debe 50 → F recibido 30 | 20 | 0 | **+20** | 0 | +20 (te deben) | n3 20⅟ | nivel-max |
| `AEXG` | debe 100 → E recibido 100 → X debe 50 → G recibido 75 | 0 | 0 | **-25** | 0 | -25 (tú debes) |  · a favor deudor 25 | nivel-max |
| `AEXI` | debe 100 → E recibido 100 → X debe 50 → I debo 50 | 50 | 50 | **+0** | 50 | +0 (al día) | — | nivel-max |
| `AEXM` | debe 100 → E recibido 100 → X debe 50 → M debe 60 | 110 | 0 | **+110** | 0 | +110 (te deben) | n3 50, n4 60 | nivel-max |
| `AEXN` | debe 100 → E recibido 100 → X debe 50 → N debo 30 | 50 | 30 | **+20** | 30 | +20 (te deben) | n3 20⅟ | nivel-max |
| `AEXR` | debe 100 → E recibido 100 → X debe 50 → R doy 50 | 50 | 0 | **+100** | 0 | +100 (te deben) | n3 50 · a favor tuyo 50 | nivel-max |
| `AEXS` | debe 100 → E recibido 100 → X debe 50 → S debo 75 | 50 | 75 | **-25** | 50 | -25 (tú debes) | n4 25⅟ | nivel-max |
| `AEYG` | debe 100 → E recibido 100 → Y debo 50 → G recibido 50 | 0 | 50 | **-100** | 0 | -100 (tú debes) | n3 50 · a favor deudor 50 | nivel-max |
| `AEYI` | debe 100 → E recibido 100 → Y debo 50 → I debe 50 | 50 | 50 | **+0** | 50 | +0 (al día) | — | nivel-max |
| `AEYM` | debe 100 → E recibido 100 → Y debo 50 → M debo 60 | 0 | 110 | **-110** | 0 | -110 (tú debes) | n3 50, n4 60 | nivel-max |
| `AEYN` | debe 100 → E recibido 100 → Y debo 50 → N debe 30 | 30 | 50 | **-20** | 30 | -20 (tú debes) | n3 20⅟ | nivel-max |
| `AEYP` | debe 100 → E recibido 100 → Y debo 50 → P doy 50 | 0 | 0 | **+0** | 0 | +0 (al día) | — | nivel-max |
| `AEYQ` | debe 100 → E recibido 100 → Y debo 50 → Q doy 30 | 0 | 20 | **-20** | 0 | -20 (tú debes) | n3 20⅟ | nivel-max |
| `AEYR` | debe 100 → E recibido 100 → Y debo 50 → R doy 75 | 0 | 0 | **+25** | 0 | +25 (te deben) |  · a favor tuyo 25 | nivel-max |
| `AEYS` | debe 100 → E recibido 100 → Y debo 50 → S debe 75 | 75 | 50 | **+25** | 50 | +25 (te deben) | n4 25⅟ | nivel-max |
| `AFEG` | debe 100 → F recibido 60 → E recibido 40 → G recibido 50 | 0 | 0 | **-50** | 0 | -50 (tú debes) |  · a favor deudor 50 | nivel-max |
| `AFER` | debe 100 → F recibido 60 → E recibido 40 → R doy 50 | 0 | 0 | **+50** | 0 | +50 (te deben) |  · a favor tuyo 50 | nivel-max |
| `AFEX` | debe 100 → F recibido 60 → E recibido 40 → X debe 50 | 50 | 0 | **+50** | 0 | +50 (te deben) | n4 50 | nivel-max |
| `AFEY` | debe 100 → F recibido 60 → E recibido 40 → Y debo 50 | 0 | 50 | **-50** | 0 | -50 (tú debes) | n4 50 | nivel-max |
| `AFGG` | debe 100 → F recibido 60 → G recibido 60 → G recibido 50 | 0 | 0 | **-70** | 0 | -70 (tú debes) |  · a favor deudor 70 | nivel-max |
| `AFGI` | debe 100 → F recibido 60 → G recibido 60 → I debe 20 | 0 | 0 | **+0** | 0 | +0 (al día) | — | nivel-max |
| `AFGM` | debe 100 → F recibido 60 → G recibido 60 → M debo 25 | 0 | 25 | **-45** | 0 | -45 (tú debes) | n4 25 · a favor deudor 20 | nivel-max |
| `AFGN` | debe 100 → F recibido 60 → G recibido 60 → N debe 10 | 0 | 0 | **-10** | 0 | -10 (tú debes) |  · a favor deudor 10 | nivel-max |
| `AFGR` | debe 100 → F recibido 60 → G recibido 60 → R doy 50 | 0 | 0 | **+30** | 0 | +30 (te deben) |  · a favor deudor 20 · a favor tuyo 50 | nivel-max |
| `AFGS` | debe 100 → F recibido 60 → G recibido 60 → S debe 30 | 10 | 0 | **+10** | 0 | +10 (te deben) | n4 10⅟ | nivel-max |
| `AFIE` | debe 100 → F recibido 60 → I debo 40 → E recibido 40 | 0 | 40 | **-40** | 0 | -40 (tú debes) | n3 40 | nivel-max |
| `AFIF` | debe 100 → F recibido 60 → I debo 40 → F recibido 20 | 20 | 40 | **-20** | 20 | -20 (tú debes) | n3 20⅟ | nivel-max |
| `AFIG` | debe 100 → F recibido 60 → I debo 40 → G recibido 60 | 0 | 40 | **-60** | 0 | -60 (tú debes) | n3 40 · a favor deudor 20 | nivel-max |
| `AFIP` | debe 100 → F recibido 60 → I debo 40 → P doy 40 | 40 | 0 | **+40** | 0 | +40 (te deben) | n1 40⅟ | nivel-max |
| `AFIQ` | debe 100 → F recibido 60 → I debo 40 → Q doy 20 | 40 | 20 | **+20** | 20 | +20 (te deben) | n1 20⅟ | nivel-max |
| `AFIR` | debe 100 → F recibido 60 → I debo 40 → R doy 60 | 40 | 0 | **+60** | 0 | +60 (te deben) | n1 40⅟ · a favor tuyo 20 | nivel-max |
| `AFIX` | debe 100 → F recibido 60 → I debo 40 → X debe 50 | 90 | 40 | **+50** | 40 | +50 (te deben) | n4 50 | nivel-max |
| `AFIY` | debe 100 → F recibido 60 → I debo 40 → Y debo 50 | 40 | 90 | **-50** | 40 | -50 (tú debes) | n4 50 | nivel-max |
| `AFME` | debe 100 → F recibido 60 → M debe 50 → E recibido 90 | 0 | 0 | **+0** | 0 | +0 (al día) | — | nivel-max |
| `AFMF` | debe 100 → F recibido 60 → M debe 50 → F recibido 50 | 40 | 0 | **+40** | 0 | +40 (te deben) | n3 40⅟ | nivel-max |
| `AFMG` | debe 100 → F recibido 60 → M debe 50 → G recibido 135 | 0 | 0 | **-45** | 0 | -45 (tú debes) |  · a favor deudor 45 | nivel-max |
| `AFMI` | debe 100 → F recibido 60 → M debe 50 → I debo 90 | 90 | 90 | **+0** | 90 | +0 (al día) | — | nivel-max |
| `AFMM` | debe 100 → F recibido 60 → M debe 50 → M debe 110 | 200 | 0 | **+200** | 0 | +200 (te deben) | n1 40⅟, n3 50, n4 110 | nivel-max |
| `AFMN` | debe 100 → F recibido 60 → M debe 50 → N debo 50 | 90 | 50 | **+40** | 50 | +40 (te deben) | n3 40⅟ | nivel-max |
| `AFMR` | debe 100 → F recibido 60 → M debe 50 → R doy 50 | 90 | 0 | **+140** | 0 | +140 (te deben) | n1 40⅟, n3 50 · a favor tuyo 50 | nivel-max |
| `AFMS` | debe 100 → F recibido 60 → M debe 50 → S debo 135 | 90 | 135 | **-45** | 90 | -45 (tú debes) | n4 45⅟ | nivel-max |
| `AFNE` | debe 100 → F recibido 60 → N debo 20 → E recibido 40 | 0 | 20 | **-20** | 0 | -20 (tú debes) | n3 20 | nivel-max |
| `AFNF` | debe 100 → F recibido 60 → N debo 20 → F recibido 20 | 20 | 20 | **+0** | 20 | +0 (al día) | — | nivel-max |
| `AFNG` | debe 100 → F recibido 60 → N debo 20 → G recibido 60 | 0 | 20 | **-40** | 0 | -40 (tú debes) | n3 20 · a favor deudor 20 | nivel-max |
| `AFNI` | debe 100 → F recibido 60 → N debo 20 → I debo 20 | 40 | 40 | **+0** | 40 | +0 (al día) | — | nivel-max |
| `AFNM` | debe 100 → F recibido 60 → N debo 20 → M debe 25 | 65 | 20 | **+45** | 20 | +45 (te deben) | n1 20⅟, n4 25 | nivel-max |
| `AFNN` | debe 100 → F recibido 60 → N debo 20 → N debo 10 | 40 | 30 | **+10** | 30 | +10 (te deben) | n1 10⅟ | nivel-max |
| `AFNP` | debe 100 → F recibido 60 → N debo 20 → P doy 20 | 40 | 0 | **+40** | 0 | +40 (te deben) | n1 40⅟ | nivel-max |
| `AFNQ` | debe 100 → F recibido 60 → N debo 20 → Q doy 10 | 40 | 10 | **+30** | 10 | +30 (te deben) | n1 30⅟ | nivel-max |
| `AFNR` | debe 100 → F recibido 60 → N debo 20 → R doy 30 | 40 | 0 | **+50** | 0 | +50 (te deben) | n1 40⅟ · a favor tuyo 10 | nivel-max |
| `AFNS` | debe 100 → F recibido 60 → N debo 20 → S debo 30 | 40 | 50 | **-10** | 40 | -10 (tú debes) | n4 10⅟ | nivel-max |
| `AFRE` | debe 100 → F recibido 60 → R doy 50 → E recibido 40 | 0 | 0 | **+50** | 0 | +50 (te deben) |  · a favor tuyo 50 | nivel-max |
| `AFRF` | debe 100 → F recibido 60 → R doy 50 → F recibido 20 | 20 | 0 | **+70** | 0 | +70 (te deben) | n1 20⅟ · a favor tuyo 50 | nivel-max |
| `AFRG` | debe 100 → F recibido 60 → R doy 50 → G recibido 60 | 0 | 0 | **+30** | 0 | +30 (te deben) |  · a favor deudor 20 · a favor tuyo 50 | nivel-max |
| `AFRI` | debe 100 → F recibido 60 → R doy 50 → I debo 90 | 40 | 40 | **+0** | 40 | +0 (al día) | — | nivel-max |
| `AFRM` | debe 100 → F recibido 60 → R doy 50 → M debe 110 | 150 | 0 | **+200** | 0 | +200 (te deben) | n1 40⅟, n4 110 · a favor tuyo 50 | nivel-max |
| `AFRN` | debe 100 → F recibido 60 → R doy 50 → N debo 50 | 40 | 0 | **+40** | 0 | +40 (te deben) | n1 40⅟ | nivel-max |
| `AFRR` | debe 100 → F recibido 60 → R doy 50 → R doy 50 | 40 | 0 | **+140** | 0 | +140 (te deben) | n1 40⅟ · a favor tuyo 100 | nivel-max |
| `AFRS` | debe 100 → F recibido 60 → R doy 50 → S debo 135 | 40 | 85 | **-45** | 40 | -45 (tú debes) | n4 45⅟ | nivel-max |
| `AFSE` | debe 100 → F recibido 60 → S debo 60 → E recibido 40 | 0 | 60 | **-60** | 0 | -60 (tú debes) | n3 60 | nivel-max |
| `AFSF` | debe 100 → F recibido 60 → S debo 60 → F recibido 20 | 20 | 60 | **-40** | 20 | -40 (tú debes) | n3 40⅟ | nivel-max |
| `AFSG` | debe 100 → F recibido 60 → S debo 60 → G recibido 60 | 0 | 60 | **-80** | 0 | -80 (tú debes) | n3 60 · a favor deudor 20 | nivel-max |
| `AFSI` | debe 100 → F recibido 60 → S debo 60 → I debe 20 | 60 | 60 | **+0** | 60 | +0 (al día) | — | nivel-max |
| `AFSM` | debe 100 → F recibido 60 → S debo 60 → M debo 25 | 40 | 85 | **-45** | 40 | -45 (tú debes) | n3 20⅟, n4 25 | nivel-max |
| `AFSN` | debe 100 → F recibido 60 → S debo 60 → N debe 10 | 50 | 60 | **-10** | 50 | -10 (tú debes) | n3 10⅟ | nivel-max |
| `AFSP` | debe 100 → F recibido 60 → S debo 60 → P doy 60 | 40 | 0 | **+40** | 0 | +40 (te deben) | n1 40⅟ | nivel-max |
| `AFSQ` | debe 100 → F recibido 60 → S debo 60 → Q doy 35 | 40 | 25 | **+15** | 25 | +15 (te deben) | n1 15⅟ | nivel-max |
| `AFSR` | debe 100 → F recibido 60 → S debo 60 → R doy 90 | 40 | 0 | **+70** | 0 | +70 (te deben) | n1 40⅟ · a favor tuyo 30 | nivel-max |
| `AFSS` | debe 100 → F recibido 60 → S debo 60 → S debe 30 | 70 | 60 | **+10** | 60 | +10 (te deben) | n4 10⅟ | nivel-max |
| `AGIG` | debe 100 → G recibido 150 → I debe 50 → G recibido 50 | 0 | 0 | **-50** | 0 | -50 (tú debes) |  · a favor deudor 50 | nivel-max |
| `AGIR` | debe 100 → G recibido 150 → I debe 50 → R doy 50 | 0 | 0 | **+50** | 0 | +50 (te deben) |  · a favor tuyo 50 | nivel-max |
| `AGIX` | debe 100 → G recibido 150 → I debe 50 → X debe 75 | 75 | 0 | **+75** | 0 | +75 (te deben) | n4 75 | nivel-max |
| `AGIY` | debe 100 → G recibido 150 → I debe 50 → Y debo 75 | 0 | 75 | **-75** | 0 | -75 (tú debes) | n4 75 | nivel-max |
| `AGMG` | debe 100 → G recibido 150 → M debo 60 → G recibido 50 | 0 | 60 | **-160** | 0 | -160 (tú debes) | n3 60 · a favor deudor 100 | nivel-max |
| `AGMI` | debe 100 → G recibido 150 → M debo 60 → I debe 110 | 60 | 60 | **+0** | 60 | +0 (al día) | — | nivel-max |
| `AGMM` | debe 100 → G recibido 150 → M debo 60 → M debo 140 | 0 | 200 | **-250** | 0 | -250 (tú debes) | n3 60, n4 140 · a favor deudor 50 | nivel-max |
| `AGMN` | debe 100 → G recibido 150 → M debo 60 → N debe 65 | 15 | 60 | **-45** | 15 | -45 (tú debes) | n3 45⅟ | nivel-max |
| `AGMP` | debe 100 → G recibido 150 → M debo 60 → P doy 60 | 0 | 0 | **-50** | 0 | -50 (tú debes) |  · a favor deudor 50 | nivel-max |
| `AGMQ` | debe 100 → G recibido 150 → M debo 60 → Q doy 35 | 0 | 25 | **-75** | 0 | -75 (tú debes) | n3 25⅟ · a favor deudor 50 | nivel-max |
| `AGMR` | debe 100 → G recibido 150 → M debo 60 → R doy 90 | 0 | 0 | **-20** | 0 | -20 (tú debes) |  · a favor deudor 50 · a favor tuyo 30 | nivel-max |
| `AGMS` | debe 100 → G recibido 150 → M debo 60 → S debe 165 | 115 | 60 | **+55** | 60 | +55 (te deben) | n4 55⅟ | nivel-max |
| `AGNG` | debe 100 → G recibido 150 → N debe 30 → G recibido 50 | 0 | 0 | **-70** | 0 | -70 (tú debes) |  · a favor deudor 70 | nivel-max |
| `AGNI` | debe 100 → G recibido 150 → N debe 30 → I debe 20 | 0 | 0 | **+0** | 0 | +0 (al día) | — | nivel-max |
| `AGNM` | debe 100 → G recibido 150 → N debe 30 → M debo 25 | 0 | 25 | **-45** | 0 | -45 (tú debes) | n4 25 · a favor deudor 20 | nivel-max |
| `AGNN` | debe 100 → G recibido 150 → N debe 30 → N debe 10 | 0 | 0 | **-10** | 0 | -10 (tú debes) |  · a favor deudor 10 | nivel-max |
| `AGNR` | debe 100 → G recibido 150 → N debe 30 → R doy 50 | 0 | 0 | **+30** | 0 | +30 (te deben) |  · a favor deudor 20 · a favor tuyo 50 | nivel-max |
| `AGNS` | debe 100 → G recibido 150 → N debe 30 → S debe 30 | 10 | 0 | **+10** | 0 | +10 (te deben) | n4 10⅟ | nivel-max |
| `AGRG` | debe 100 → G recibido 150 → R doy 50 → G recibido 50 | 0 | 0 | **-50** | 0 | -50 (tú debes) |  · a favor deudor 100 · a favor tuyo 50 | nivel-max |
| `AGRR` | debe 100 → G recibido 150 → R doy 50 → R doy 50 | 0 | 0 | **+50** | 0 | +50 (te deben) |  · a favor deudor 50 · a favor tuyo 100 | nivel-max |
| `AGRX` | debe 100 → G recibido 150 → R doy 50 → X debe 50 | 0 | 0 | **+50** | 0 | +50 (te deben) |  · a favor tuyo 50 | nivel-max |
| `AGRY` | debe 100 → G recibido 150 → R doy 50 → Y debo 50 | 0 | 0 | **-50** | 0 | -50 (tú debes) |  · a favor deudor 50 | nivel-max |
| `AGSE` | debe 100 → G recibido 150 → S debe 75 → E recibido 25 | 0 | 0 | **+0** | 0 | +0 (al día) | — | nivel-max |
| `AGSF` | debe 100 → G recibido 150 → S debe 75 → F recibido 15 | 10 | 0 | **+10** | 0 | +10 (te deben) | n3 10⅟ | nivel-max |
| `AGSG` | debe 100 → G recibido 150 → S debe 75 → G recibido 40 | 0 | 0 | **-15** | 0 | -15 (tú debes) |  · a favor deudor 15 | nivel-max |
| `AGSI` | debe 100 → G recibido 150 → S debe 75 → I debo 25 | 25 | 25 | **+0** | 25 | +0 (al día) | — | nivel-max |
| `AGSM` | debe 100 → G recibido 150 → S debe 75 → M debe 30 | 55 | 0 | **+55** | 0 | +55 (te deben) | n3 25⅟, n4 30 | nivel-max |
| `AGSN` | debe 100 → G recibido 150 → S debe 75 → N debo 15 | 25 | 15 | **+10** | 15 | +10 (te deben) | n3 10⅟ | nivel-max |
| `AGSR` | debe 100 → G recibido 150 → S debe 75 → R doy 50 | 25 | 0 | **+75** | 0 | +75 (te deben) | n3 25⅟ · a favor tuyo 50 | nivel-max |
| `AGSS` | debe 100 → G recibido 150 → S debe 75 → S debo 40 | 25 | 40 | **-15** | 25 | -15 (tú debes) | n4 15⅟ | nivel-max |
| `AIEG` | debe 100 → I debo 100 → E recibido 100 → G recibido 50 | 0 | 100 | **-150** | 0 | -150 (tú debes) | n2 100 · a favor deudor 50 | nivel-max |
| `AIEI` | debe 100 → I debo 100 → E recibido 100 → I debe 100 | 100 | 100 | **+0** | 100 | +0 (al día) | — | nivel-max |
| `AIEM` | debe 100 → I debo 100 → E recibido 100 → M debo 125 | 0 | 225 | **-225** | 0 | -225 (tú debes) | n2 100, n4 125 | nivel-max |
| `AIEN` | debe 100 → I debo 100 → E recibido 100 → N debe 60 | 60 | 100 | **-40** | 60 | -40 (tú debes) | n2 40⅟ | nivel-max |
| `AIEP` | debe 100 → I debo 100 → E recibido 100 → P doy 100 | 0 | 0 | **+0** | 0 | +0 (al día) | — | nivel-max |
| `AIEQ` | debe 100 → I debo 100 → E recibido 100 → Q doy 60 | 0 | 40 | **-40** | 0 | -40 (tú debes) | n2 40⅟ | nivel-max |
| `AIER` | debe 100 → I debo 100 → E recibido 100 → R doy 150 | 0 | 0 | **+50** | 0 | +50 (te deben) |  · a favor tuyo 50 | nivel-max |
| `AIES` | debe 100 → I debo 100 → E recibido 100 → S debe 150 | 150 | 100 | **+50** | 100 | +50 (te deben) | n4 50⅟ | nivel-max |
| `AIFE` | debe 100 → I debo 100 → F recibido 60 → E recibido 40 | 0 | 100 | **-100** | 0 | -100 (tú debes) | n2 100 | nivel-max |
| `AIFF` | debe 100 → I debo 100 → F recibido 60 → F recibido 20 | 20 | 100 | **-80** | 20 | -80 (tú debes) | n2 80⅟ | nivel-max |
| `AIFG` | debe 100 → I debo 100 → F recibido 60 → G recibido 60 | 0 | 100 | **-120** | 0 | -120 (tú debes) | n2 100 · a favor deudor 20 | nivel-max |
| `AIFI` | debe 100 → I debo 100 → F recibido 60 → I debe 60 | 100 | 100 | **+0** | 100 | +0 (al día) | — | nivel-max |
| `AIFM` | debe 100 → I debo 100 → F recibido 60 → M debo 75 | 40 | 175 | **-135** | 40 | -135 (tú debes) | n2 60⅟, n4 75 | nivel-max |
| `AIFN` | debe 100 → I debo 100 → F recibido 60 → N debe 35 | 75 | 100 | **-25** | 75 | -25 (tú debes) | n2 25⅟ | nivel-max |
| `AIFP` | debe 100 → I debo 100 → F recibido 60 → P doy 100 | 40 | 0 | **+40** | 0 | +40 (te deben) | n1 40⅟ | nivel-max |
| `AIFQ` | debe 100 → I debo 100 → F recibido 60 → Q doy 60 | 40 | 40 | **+0** | 40 | +0 (al día) | — | nivel-max |
| `AIFR` | debe 100 → I debo 100 → F recibido 60 → R doy 150 | 40 | 0 | **+90** | 0 | +90 (te deben) | n1 40⅟ · a favor tuyo 50 | nivel-max |
| `AIFS` | debe 100 → I debo 100 → F recibido 60 → S debe 90 | 130 | 100 | **+30** | 100 | +30 (te deben) | n4 30⅟ | nivel-max |
| `AIGG` | debe 100 → I debo 100 → G recibido 150 → G recibido 50 | 0 | 100 | **-200** | 0 | -200 (tú debes) | n2 100 · a favor deudor 100 | nivel-max |
| `AIGI` | debe 100 → I debo 100 → G recibido 150 → I debe 150 | 100 | 100 | **+0** | 100 | +0 (al día) | — | nivel-max |
| `AIGM` | debe 100 → I debo 100 → G recibido 150 → M debo 190 | 0 | 290 | **-340** | 0 | -340 (tú debes) | n2 100, n4 190 · a favor deudor 50 | nivel-max |
| `AIGN` | debe 100 → I debo 100 → G recibido 150 → N debe 90 | 40 | 100 | **-60** | 40 | -60 (tú debes) | n2 60⅟ | nivel-max |
| `AIGP` | debe 100 → I debo 100 → G recibido 150 → P doy 100 | 0 | 0 | **-50** | 0 | -50 (tú debes) |  · a favor deudor 50 | nivel-max |
| `AIGQ` | debe 100 → I debo 100 → G recibido 150 → Q doy 60 | 0 | 40 | **-90** | 0 | -90 (tú debes) | n2 40⅟ · a favor deudor 50 | nivel-max |
| `AIGR` | debe 100 → I debo 100 → G recibido 150 → R doy 150 | 0 | 0 | **+0** | 0 | +0 (al día) |  · a favor deudor 50 · a favor tuyo 50 | nivel-max |
| `AIGS` | debe 100 → I debo 100 → G recibido 150 → S debe 225 | 175 | 100 | **+75** | 100 | +75 (te deben) | n4 75⅟ | nivel-max |
| `AIPE` | debe 100 → I debo 100 → P doy 100 → E recibido 100 | 0 | 0 | **+0** | 0 | +0 (al día) | — | nivel-max |
| `AIPF` | debe 100 → I debo 100 → P doy 100 → F recibido 60 | 40 | 0 | **+40** | 0 | +40 (te deben) | n1 40⅟ | nivel-max |
| `AIPG` | debe 100 → I debo 100 → P doy 100 → G recibido 150 | 0 | 0 | **-50** | 0 | -50 (tú debes) |  · a favor deudor 50 | nivel-max |
| `AIPI` | debe 100 → I debo 100 → P doy 100 → I debo 100 | 100 | 100 | **+0** | 100 | +0 (al día) | — | nivel-max |
| `AIPM` | debe 100 → I debo 100 → P doy 100 → M debe 125 | 225 | 0 | **+225** | 0 | +225 (te deben) | n1 100, n4 125 | nivel-max |
| `AIPN` | debe 100 → I debo 100 → P doy 100 → N debo 60 | 100 | 60 | **+40** | 60 | +40 (te deben) | n1 40⅟ | nivel-max |
| `AIPR` | debe 100 → I debo 100 → P doy 100 → R doy 50 | 100 | 0 | **+150** | 0 | +150 (te deben) | n1 100 · a favor tuyo 50 | nivel-max |
| `AIPS` | debe 100 → I debo 100 → P doy 100 → S debo 150 | 100 | 150 | **-50** | 100 | -50 (tú debes) | n4 50⅟ | nivel-max |
| `AIQE` | debe 100 → I debo 100 → Q doy 60 → E recibido 100 | 0 | 40 | **-40** | 0 | -40 (tú debes) | n2 40⅟ | nivel-max |
| `AIQF` | debe 100 → I debo 100 → Q doy 60 → F recibido 60 | 40 | 40 | **+0** | 40 | +0 (al día) | — | nivel-max |
| `AIQG` | debe 100 → I debo 100 → Q doy 60 → G recibido 150 | 0 | 40 | **-90** | 0 | -90 (tú debes) | n2 40⅟ · a favor deudor 50 | nivel-max |
| `AIQI` | debe 100 → I debo 100 → Q doy 60 → I debo 60 | 100 | 100 | **+0** | 100 | +0 (al día) | — | nivel-max |
| `AIQM` | debe 100 → I debo 100 → Q doy 60 → M debe 75 | 175 | 40 | **+135** | 40 | +135 (te deben) | n1 60⅟, n4 75 | nivel-max |
| `AIQN` | debe 100 → I debo 100 → Q doy 60 → N debo 35 | 100 | 75 | **+25** | 75 | +25 (te deben) | n1 25⅟ | nivel-max |
| `AIQP` | debe 100 → I debo 100 → Q doy 60 → P doy 40 | 100 | 0 | **+100** | 0 | +100 (te deben) | n1 100 | nivel-max |
| `AIQQ` | debe 100 → I debo 100 → Q doy 60 → Q doy 20 | 100 | 20 | **+80** | 20 | +80 (te deben) | n1 80⅟ | nivel-max |
| `AIQR` | debe 100 → I debo 100 → Q doy 60 → R doy 60 | 100 | 0 | **+120** | 0 | +120 (te deben) | n1 100 · a favor tuyo 20 | nivel-max |
| `AIQS` | debe 100 → I debo 100 → Q doy 60 → S debo 90 | 100 | 130 | **-30** | 100 | -30 (tú debes) | n4 30⅟ | nivel-max |
| `AIRE` | debe 100 → I debo 100 → R doy 150 → E recibido 100 | 0 | 0 | **+50** | 0 | +50 (te deben) |  · a favor tuyo 50 | nivel-max |
| `AIRF` | debe 100 → I debo 100 → R doy 150 → F recibido 60 | 40 | 0 | **+90** | 0 | +90 (te deben) | n1 40⅟ · a favor tuyo 50 | nivel-max |
| `AIRG` | debe 100 → I debo 100 → R doy 150 → G recibido 150 | 0 | 0 | **+0** | 0 | +0 (al día) |  · a favor deudor 50 · a favor tuyo 50 | nivel-max |
| `AIRI` | debe 100 → I debo 100 → R doy 150 → I debo 150 | 100 | 100 | **+0** | 100 | +0 (al día) | — | nivel-max |
| `AIRM` | debe 100 → I debo 100 → R doy 150 → M debe 190 | 290 | 0 | **+340** | 0 | +340 (te deben) | n1 100, n4 190 · a favor tuyo 50 | nivel-max |
| `AIRN` | debe 100 → I debo 100 → R doy 150 → N debo 90 | 100 | 40 | **+60** | 40 | +60 (te deben) | n1 60⅟ | nivel-max |
| `AIRR` | debe 100 → I debo 100 → R doy 150 → R doy 50 | 100 | 0 | **+200** | 0 | +200 (te deben) | n1 100 · a favor tuyo 100 | nivel-max |
| `AIRS` | debe 100 → I debo 100 → R doy 150 → S debo 225 | 100 | 175 | **-75** | 100 | -75 (tú debes) | n4 75⅟ | nivel-max |
| `AIXE` | debe 100 → I debo 100 → X debe 50 → E recibido 150 | 0 | 100 | **-100** | 0 | -100 (tú debes) | n2 100 | nivel-max |
| `AIXF` | debe 100 → I debo 100 → X debe 50 → F recibido 90 | 60 | 100 | **-40** | 60 | -40 (tú debes) | n2 40⅟ | nivel-max |
| `AIXG` | debe 100 → I debo 100 → X debe 50 → G recibido 225 | 0 | 100 | **-175** | 0 | -175 (tú debes) | n2 100 · a favor deudor 75 | nivel-max |
| `AIXI` | debe 100 → I debo 100 → X debe 50 → I debo 50 | 150 | 150 | **+0** | 150 | +0 (al día) | — | nivel-max |
| `AIXM` | debe 100 → I debo 100 → X debe 50 → M debe 60 | 210 | 100 | **+110** | 100 | +110 (te deben) | n3 50, n4 60 | nivel-max |
| `AIXN` | debe 100 → I debo 100 → X debe 50 → N debo 30 | 150 | 130 | **+20** | 130 | +20 (te deben) | n3 20⅟ | nivel-max |
| `AIXP` | debe 100 → I debo 100 → X debe 50 → P doy 100 | 150 | 0 | **+150** | 0 | +150 (te deben) | n1 100, n3 50 | nivel-max |
| `AIXQ` | debe 100 → I debo 100 → X debe 50 → Q doy 60 | 150 | 40 | **+110** | 40 | +110 (te deben) | n1 60⅟, n3 50 | nivel-max |
| `AIXR` | debe 100 → I debo 100 → X debe 50 → R doy 150 | 150 | 0 | **+200** | 0 | +200 (te deben) | n1 100, n3 50 · a favor tuyo 50 | nivel-max |
| `AIXS` | debe 100 → I debo 100 → X debe 50 → S debo 75 | 150 | 175 | **-25** | 150 | -25 (tú debes) | n4 25⅟ | nivel-max |
| `AIYE` | debe 100 → I debo 100 → Y debo 50 → E recibido 100 | 0 | 150 | **-150** | 0 | -150 (tú debes) | n2 100, n3 50 | nivel-max |
| `AIYF` | debe 100 → I debo 100 → Y debo 50 → F recibido 60 | 40 | 150 | **-110** | 40 | -110 (tú debes) | n2 60⅟, n3 50 | nivel-max |
| `AIYG` | debe 100 → I debo 100 → Y debo 50 → G recibido 150 | 0 | 150 | **-200** | 0 | -200 (tú debes) | n2 100, n3 50 · a favor deudor 50 | nivel-max |
| `AIYI` | debe 100 → I debo 100 → Y debo 50 → I debe 50 | 150 | 150 | **+0** | 150 | +0 (al día) | — | nivel-max |
| `AIYM` | debe 100 → I debo 100 → Y debo 50 → M debo 60 | 100 | 210 | **-110** | 100 | -110 (tú debes) | n3 50, n4 60 | nivel-max |
| `AIYN` | debe 100 → I debo 100 → Y debo 50 → N debe 30 | 130 | 150 | **-20** | 130 | -20 (tú debes) | n3 20⅟ | nivel-max |
| `AIYP` | debe 100 → I debo 100 → Y debo 50 → P doy 150 | 100 | 0 | **+100** | 0 | +100 (te deben) | n1 100 | nivel-max |
| `AIYQ` | debe 100 → I debo 100 → Y debo 50 → Q doy 90 | 100 | 60 | **+40** | 60 | +40 (te deben) | n1 40⅟ | nivel-max |
| `AIYR` | debe 100 → I debo 100 → Y debo 50 → R doy 225 | 100 | 0 | **+175** | 0 | +175 (te deben) | n1 100 · a favor tuyo 75 | nivel-max |
| `AIYS` | debe 100 → I debo 100 → Y debo 50 → S debe 75 | 175 | 150 | **+25** | 150 | +25 (te deben) | n4 25⅟ | nivel-max |
| `ANEG` | debe 100 → N debo 60 → E recibido 100 → G recibido 50 | 0 | 60 | **-110** | 0 | -110 (tú debes) | n2 60 · a favor deudor 50 | nivel-max |
| `ANEI` | debe 100 → N debo 60 → E recibido 100 → I debe 60 | 60 | 60 | **+0** | 60 | +0 (al día) | — | nivel-max |
| `ANEM` | debe 100 → N debo 60 → E recibido 100 → M debo 75 | 0 | 135 | **-135** | 0 | -135 (tú debes) | n2 60, n4 75 | nivel-max |
| `ANEN` | debe 100 → N debo 60 → E recibido 100 → N debe 35 | 35 | 60 | **-25** | 35 | -25 (tú debes) | n2 25⅟ | nivel-max |
| `ANEP` | debe 100 → N debo 60 → E recibido 100 → P doy 60 | 0 | 0 | **+0** | 0 | +0 (al día) | — | nivel-max |
| `ANEQ` | debe 100 → N debo 60 → E recibido 100 → Q doy 35 | 0 | 25 | **-25** | 0 | -25 (tú debes) | n2 25⅟ | nivel-max |
| `ANER` | debe 100 → N debo 60 → E recibido 100 → R doy 90 | 0 | 0 | **+30** | 0 | +30 (te deben) |  · a favor tuyo 30 | nivel-max |
| `ANES` | debe 100 → N debo 60 → E recibido 100 → S debe 90 | 90 | 60 | **+30** | 60 | +30 (te deben) | n4 30⅟ | nivel-max |
| `ANFE` | debe 100 → N debo 60 → F recibido 60 → E recibido 40 | 0 | 60 | **-60** | 0 | -60 (tú debes) | n2 60 | nivel-max |
| `ANFF` | debe 100 → N debo 60 → F recibido 60 → F recibido 20 | 20 | 60 | **-40** | 20 | -40 (tú debes) | n2 40⅟ | nivel-max |
| `ANFG` | debe 100 → N debo 60 → F recibido 60 → G recibido 60 | 0 | 60 | **-80** | 0 | -80 (tú debes) | n2 60 · a favor deudor 20 | nivel-max |
| `ANFI` | debe 100 → N debo 60 → F recibido 60 → I debe 20 | 60 | 60 | **+0** | 60 | +0 (al día) | — | nivel-max |
| `ANFM` | debe 100 → N debo 60 → F recibido 60 → M debo 25 | 40 | 85 | **-45** | 40 | -45 (tú debes) | n2 20⅟, n4 25 | nivel-max |
| `ANFN` | debe 100 → N debo 60 → F recibido 60 → N debe 10 | 50 | 60 | **-10** | 50 | -10 (tú debes) | n2 10⅟ | nivel-max |
| `ANFP` | debe 100 → N debo 60 → F recibido 60 → P doy 60 | 40 | 0 | **+40** | 0 | +40 (te deben) | n1 40⅟ | nivel-max |
| `ANFQ` | debe 100 → N debo 60 → F recibido 60 → Q doy 35 | 40 | 25 | **+15** | 25 | +15 (te deben) | n1 15⅟ | nivel-max |
| `ANFR` | debe 100 → N debo 60 → F recibido 60 → R doy 90 | 40 | 0 | **+70** | 0 | +70 (te deben) | n1 40⅟ · a favor tuyo 30 | nivel-max |
| `ANFS` | debe 100 → N debo 60 → F recibido 60 → S debe 30 | 70 | 60 | **+10** | 60 | +10 (te deben) | n4 10⅟ | nivel-max |
| `ANGG` | debe 100 → N debo 60 → G recibido 150 → G recibido 50 | 0 | 60 | **-160** | 0 | -160 (tú debes) | n2 60 · a favor deudor 100 | nivel-max |
| `ANGI` | debe 100 → N debo 60 → G recibido 150 → I debe 110 | 60 | 60 | **+0** | 60 | +0 (al día) | — | nivel-max |
| `ANGM` | debe 100 → N debo 60 → G recibido 150 → M debo 140 | 0 | 200 | **-250** | 0 | -250 (tú debes) | n2 60, n4 140 · a favor deudor 50 | nivel-max |
| `ANGN` | debe 100 → N debo 60 → G recibido 150 → N debe 65 | 15 | 60 | **-45** | 15 | -45 (tú debes) | n2 45⅟ | nivel-max |
| `ANGP` | debe 100 → N debo 60 → G recibido 150 → P doy 60 | 0 | 0 | **-50** | 0 | -50 (tú debes) |  · a favor deudor 50 | nivel-max |
| `ANGQ` | debe 100 → N debo 60 → G recibido 150 → Q doy 35 | 0 | 25 | **-75** | 0 | -75 (tú debes) | n2 25⅟ · a favor deudor 50 | nivel-max |
| `ANGR` | debe 100 → N debo 60 → G recibido 150 → R doy 90 | 0 | 0 | **-20** | 0 | -20 (tú debes) |  · a favor deudor 50 · a favor tuyo 30 | nivel-max |
| `ANGS` | debe 100 → N debo 60 → G recibido 150 → S debe 165 | 115 | 60 | **+55** | 60 | +55 (te deben) | n4 55⅟ | nivel-max |
| `ANIE` | debe 100 → N debo 60 → I debo 40 → E recibido 100 | 0 | 100 | **-100** | 0 | -100 (tú debes) | n2 60, n3 40 | nivel-max |
| `ANIF` | debe 100 → N debo 60 → I debo 40 → F recibido 60 | 40 | 100 | **-60** | 40 | -60 (tú debes) | n2 20⅟, n3 40 | nivel-max |
| `ANIG` | debe 100 → N debo 60 → I debo 40 → G recibido 150 | 0 | 100 | **-150** | 0 | -150 (tú debes) | n2 60, n3 40 · a favor deudor 50 | nivel-max |
| `ANIP` | debe 100 → N debo 60 → I debo 40 → P doy 100 | 100 | 0 | **+100** | 0 | +100 (te deben) | n1 100 | nivel-max |
| `ANIQ` | debe 100 → N debo 60 → I debo 40 → Q doy 60 | 100 | 40 | **+60** | 40 | +60 (te deben) | n1 60⅟ | nivel-max |
| `ANIR` | debe 100 → N debo 60 → I debo 40 → R doy 150 | 100 | 0 | **+150** | 0 | +150 (te deben) | n1 100 · a favor tuyo 50 | nivel-max |
| `ANIX` | debe 100 → N debo 60 → I debo 40 → X debe 50 | 150 | 100 | **+50** | 100 | +50 (te deben) | n4 50 | nivel-max |
| `ANIY` | debe 100 → N debo 60 → I debo 40 → Y debo 50 | 100 | 150 | **-50** | 100 | -50 (tú debes) | n4 50 | nivel-max |
| `ANME` | debe 100 → N debo 60 → M debe 50 → E recibido 150 | 0 | 60 | **-60** | 0 | -60 (tú debes) | n2 60 | nivel-max |
| `ANMF` | debe 100 → N debo 60 → M debe 50 → F recibido 90 | 60 | 60 | **+0** | 60 | +0 (al día) | — | nivel-max |
| `ANMG` | debe 100 → N debo 60 → M debe 50 → G recibido 225 | 0 | 60 | **-135** | 0 | -135 (tú debes) | n2 60 · a favor deudor 75 | nivel-max |
| `ANMI` | debe 100 → N debo 60 → M debe 50 → I debo 90 | 150 | 150 | **+0** | 150 | +0 (al día) | — | nivel-max |
| `ANMM` | debe 100 → N debo 60 → M debe 50 → M debe 110 | 260 | 60 | **+200** | 60 | +200 (te deben) | n1 40⅟, n3 50, n4 110 | nivel-max |
| `ANMN` | debe 100 → N debo 60 → M debe 50 → N debo 50 | 150 | 110 | **+40** | 110 | +40 (te deben) | n3 40⅟ | nivel-max |
| `ANMP` | debe 100 → N debo 60 → M debe 50 → P doy 60 | 150 | 0 | **+150** | 0 | +150 (te deben) | n1 100, n3 50 | nivel-max |
| `ANMQ` | debe 100 → N debo 60 → M debe 50 → Q doy 35 | 150 | 25 | **+125** | 25 | +125 (te deben) | n1 75⅟, n3 50 | nivel-max |
| `ANMR` | debe 100 → N debo 60 → M debe 50 → R doy 90 | 150 | 0 | **+180** | 0 | +180 (te deben) | n1 100, n3 50 · a favor tuyo 30 | nivel-max |
| `ANMS` | debe 100 → N debo 60 → M debe 50 → S debo 135 | 150 | 195 | **-45** | 150 | -45 (tú debes) | n4 45⅟ | nivel-max |
| `ANPE` | debe 100 → N debo 60 → P doy 60 → E recibido 100 | 0 | 0 | **+0** | 0 | +0 (al día) | — | nivel-max |
| `ANPF` | debe 100 → N debo 60 → P doy 60 → F recibido 60 | 40 | 0 | **+40** | 0 | +40 (te deben) | n1 40⅟ | nivel-max |
| `ANPG` | debe 100 → N debo 60 → P doy 60 → G recibido 150 | 0 | 0 | **-50** | 0 | -50 (tú debes) |  · a favor deudor 50 | nivel-max |
| `ANPI` | debe 100 → N debo 60 → P doy 60 → I debo 100 | 100 | 100 | **+0** | 100 | +0 (al día) | — | nivel-max |
| `ANPM` | debe 100 → N debo 60 → P doy 60 → M debe 125 | 225 | 0 | **+225** | 0 | +225 (te deben) | n1 100, n4 125 | nivel-max |
| `ANPN` | debe 100 → N debo 60 → P doy 60 → N debo 60 | 100 | 60 | **+40** | 60 | +40 (te deben) | n1 40⅟ | nivel-max |
| `ANPR` | debe 100 → N debo 60 → P doy 60 → R doy 50 | 100 | 0 | **+150** | 0 | +150 (te deben) | n1 100 · a favor tuyo 50 | nivel-max |
| `ANPS` | debe 100 → N debo 60 → P doy 60 → S debo 150 | 100 | 150 | **-50** | 100 | -50 (tú debes) | n4 50⅟ | nivel-max |
| `ANQE` | debe 100 → N debo 60 → Q doy 35 → E recibido 100 | 0 | 25 | **-25** | 0 | -25 (tú debes) | n2 25⅟ | nivel-max |
| `ANQF` | debe 100 → N debo 60 → Q doy 35 → F recibido 60 | 40 | 25 | **+15** | 25 | +15 (te deben) | n1 15⅟ | nivel-max |
| `ANQG` | debe 100 → N debo 60 → Q doy 35 → G recibido 150 | 0 | 25 | **-75** | 0 | -75 (tú debes) | n2 25⅟ · a favor deudor 50 | nivel-max |
| `ANQI` | debe 100 → N debo 60 → Q doy 35 → I debo 75 | 100 | 100 | **+0** | 100 | +0 (al día) | — | nivel-max |
| `ANQM` | debe 100 → N debo 60 → Q doy 35 → M debe 95 | 195 | 25 | **+170** | 25 | +170 (te deben) | n1 75⅟, n4 95 | nivel-max |
| `ANQN` | debe 100 → N debo 60 → Q doy 35 → N debo 45 | 100 | 70 | **+30** | 70 | +30 (te deben) | n1 30⅟ | nivel-max |
| `ANQP` | debe 100 → N debo 60 → Q doy 35 → P doy 25 | 100 | 0 | **+100** | 0 | +100 (te deben) | n1 100 | nivel-max |
| `ANQQ` | debe 100 → N debo 60 → Q doy 35 → Q doy 15 | 100 | 10 | **+90** | 10 | +90 (te deben) | n1 90⅟ | nivel-max |
| `ANQR` | debe 100 → N debo 60 → Q doy 35 → R doy 40 | 100 | 0 | **+115** | 0 | +115 (te deben) | n1 100 · a favor tuyo 15 | nivel-max |
| `ANQS` | debe 100 → N debo 60 → Q doy 35 → S debo 115 | 100 | 140 | **-40** | 100 | -40 (tú debes) | n4 40⅟ | nivel-max |
| `ANRE` | debe 100 → N debo 60 → R doy 90 → E recibido 100 | 0 | 0 | **+30** | 0 | +30 (te deben) |  · a favor tuyo 30 | nivel-max |
| `ANRF` | debe 100 → N debo 60 → R doy 90 → F recibido 60 | 40 | 0 | **+70** | 0 | +70 (te deben) | n1 40⅟ · a favor tuyo 30 | nivel-max |
| `ANRG` | debe 100 → N debo 60 → R doy 90 → G recibido 150 | 0 | 0 | **-20** | 0 | -20 (tú debes) |  · a favor deudor 50 · a favor tuyo 30 | nivel-max |
| `ANRI` | debe 100 → N debo 60 → R doy 90 → I debo 130 | 100 | 100 | **+0** | 100 | +0 (al día) | — | nivel-max |
| `ANRM` | debe 100 → N debo 60 → R doy 90 → M debe 160 | 260 | 0 | **+290** | 0 | +290 (te deben) | n1 100, n4 160 · a favor tuyo 30 | nivel-max |
| `ANRN` | debe 100 → N debo 60 → R doy 90 → N debo 75 | 100 | 45 | **+55** | 45 | +55 (te deben) | n1 55⅟ | nivel-max |
| `ANRR` | debe 100 → N debo 60 → R doy 90 → R doy 50 | 100 | 0 | **+180** | 0 | +180 (te deben) | n1 100 · a favor tuyo 80 | nivel-max |
| `ANRS` | debe 100 → N debo 60 → R doy 90 → S debo 195 | 100 | 165 | **-65** | 100 | -65 (tú debes) | n4 65⅟ | nivel-max |
| `ANSE` | debe 100 → N debo 60 → S debo 60 → E recibido 100 | 0 | 120 | **-120** | 0 | -120 (tú debes) | n2 60, n3 60 | nivel-max |
| `ANSF` | debe 100 → N debo 60 → S debo 60 → F recibido 60 | 40 | 120 | **-80** | 40 | -80 (tú debes) | n2 20⅟, n3 60 | nivel-max |
| `ANSG` | debe 100 → N debo 60 → S debo 60 → G recibido 150 | 0 | 120 | **-170** | 0 | -170 (tú debes) | n2 60, n3 60 · a favor deudor 50 | nivel-max |
| `ANSI` | debe 100 → N debo 60 → S debo 60 → I debe 20 | 120 | 120 | **+0** | 120 | +0 (al día) | — | nivel-max |
| `ANSM` | debe 100 → N debo 60 → S debo 60 → M debo 25 | 100 | 145 | **-45** | 100 | -45 (tú debes) | n3 20⅟, n4 25 | nivel-max |
| `ANSN` | debe 100 → N debo 60 → S debo 60 → N debe 10 | 110 | 120 | **-10** | 110 | -10 (tú debes) | n3 10⅟ | nivel-max |
| `ANSP` | debe 100 → N debo 60 → S debo 60 → P doy 120 | 100 | 0 | **+100** | 0 | +100 (te deben) | n1 100 | nivel-max |
| `ANSQ` | debe 100 → N debo 60 → S debo 60 → Q doy 70 | 100 | 50 | **+50** | 50 | +50 (te deben) | n1 50⅟ | nivel-max |
| `ANSR` | debe 100 → N debo 60 → S debo 60 → R doy 180 | 100 | 0 | **+160** | 0 | +160 (te deben) | n1 100 · a favor tuyo 60 | nivel-max |
| `ANSS` | debe 100 → N debo 60 → S debo 60 → S debe 30 | 130 | 120 | **+10** | 120 | +10 (te deben) | n4 10⅟ | nivel-max |
| `AREG` | debe 100 → R doy 50 → E recibido 100 → G recibido 50 | 0 | 0 | **+0** | 0 | +0 (al día) |  · a favor deudor 50 · a favor tuyo 50 | nivel-max |
| `AREI` | debe 100 → R doy 50 → E recibido 100 → I debo 50 | 0 | 0 | **+0** | 0 | +0 (al día) | — | nivel-max |
| `AREM` | debe 100 → R doy 50 → E recibido 100 → M debe 60 | 60 | 0 | **+110** | 0 | +110 (te deben) | n4 60 · a favor tuyo 50 | nivel-max |
| `AREN` | debe 100 → R doy 50 → E recibido 100 → N debo 30 | 0 | 0 | **+20** | 0 | +20 (te deben) |  · a favor tuyo 20 | nivel-max |
| `ARER` | debe 100 → R doy 50 → E recibido 100 → R doy 50 | 0 | 0 | **+100** | 0 | +100 (te deben) |  · a favor tuyo 100 | nivel-max |
| `ARES` | debe 100 → R doy 50 → E recibido 100 → S debo 75 | 0 | 25 | **-25** | 0 | -25 (tú debes) | n4 25⅟ | nivel-max |
| `ARFE` | debe 100 → R doy 50 → F recibido 60 → E recibido 40 | 0 | 0 | **+50** | 0 | +50 (te deben) |  · a favor tuyo 50 | nivel-max |
| `ARFF` | debe 100 → R doy 50 → F recibido 60 → F recibido 20 | 20 | 0 | **+70** | 0 | +70 (te deben) | n1 20⅟ · a favor tuyo 50 | nivel-max |
| `ARFG` | debe 100 → R doy 50 → F recibido 60 → G recibido 60 | 0 | 0 | **+30** | 0 | +30 (te deben) |  · a favor deudor 20 · a favor tuyo 50 | nivel-max |
| `ARFI` | debe 100 → R doy 50 → F recibido 60 → I debo 90 | 40 | 40 | **+0** | 40 | +0 (al día) | — | nivel-max |
| `ARFM` | debe 100 → R doy 50 → F recibido 60 → M debe 110 | 150 | 0 | **+200** | 0 | +200 (te deben) | n1 40⅟, n4 110 · a favor tuyo 50 | nivel-max |
| `ARFN` | debe 100 → R doy 50 → F recibido 60 → N debo 50 | 40 | 0 | **+40** | 0 | +40 (te deben) | n1 40⅟ | nivel-max |
| `ARFR` | debe 100 → R doy 50 → F recibido 60 → R doy 50 | 40 | 0 | **+140** | 0 | +140 (te deben) | n1 40⅟ · a favor tuyo 100 | nivel-max |
| `ARFS` | debe 100 → R doy 50 → F recibido 60 → S debo 135 | 40 | 85 | **-45** | 40 | -45 (tú debes) | n4 45⅟ | nivel-max |
| `ARGG` | debe 100 → R doy 50 → G recibido 150 → G recibido 50 | 0 | 0 | **-50** | 0 | -50 (tú debes) |  · a favor deudor 100 · a favor tuyo 50 | nivel-max |
| `ARGR` | debe 100 → R doy 50 → G recibido 150 → R doy 50 | 0 | 0 | **+50** | 0 | +50 (te deben) |  · a favor deudor 50 · a favor tuyo 100 | nivel-max |
| `ARGX` | debe 100 → R doy 50 → G recibido 150 → X debe 50 | 0 | 0 | **+50** | 0 | +50 (te deben) |  · a favor tuyo 50 | nivel-max |
| `ARGY` | debe 100 → R doy 50 → G recibido 150 → Y debo 50 | 0 | 0 | **-50** | 0 | -50 (tú debes) |  · a favor deudor 50 | nivel-max |
| `ARIE` | debe 100 → R doy 50 → I debo 150 → E recibido 100 | 0 | 100 | **-100** | 0 | -100 (tú debes) | n3 100⅟ | nivel-max |
| `ARIF` | debe 100 → R doy 50 → I debo 150 → F recibido 60 | 40 | 100 | **-60** | 40 | -60 (tú debes) | n3 60⅟ | nivel-max |
| `ARIG` | debe 100 → R doy 50 → I debo 150 → G recibido 150 | 0 | 100 | **-150** | 0 | -150 (tú debes) | n3 100⅟ · a favor deudor 50 | nivel-max |
| `ARIP` | debe 100 → R doy 50 → I debo 150 → P doy 100 | 100 | 0 | **+100** | 0 | +100 (te deben) | n1 100 | nivel-max |
| `ARIQ` | debe 100 → R doy 50 → I debo 150 → Q doy 60 | 100 | 40 | **+60** | 40 | +60 (te deben) | n1 60⅟ | nivel-max |
| `ARIR` | debe 100 → R doy 50 → I debo 150 → R doy 150 | 100 | 0 | **+150** | 0 | +150 (te deben) | n1 100 · a favor tuyo 50 | nivel-max |
| `ARIX` | debe 100 → R doy 50 → I debo 150 → X debe 50 | 150 | 100 | **+50** | 100 | +50 (te deben) | n4 50 | nivel-max |
| `ARIY` | debe 100 → R doy 50 → I debo 150 → Y debo 50 | 100 | 150 | **-50** | 100 | -50 (tú debes) | n4 50 | nivel-max |
| `ARME` | debe 100 → R doy 50 → M debe 190 → E recibido 290 | 0 | 0 | **+50** | 0 | +50 (te deben) |  · a favor tuyo 50 | nivel-max |
| `ARMF` | debe 100 → R doy 50 → M debe 190 → F recibido 170 | 120 | 0 | **+170** | 0 | +170 (te deben) | n3 120⅟ · a favor tuyo 50 | nivel-max |
| `ARMG` | debe 100 → R doy 50 → M debe 190 → G recibido 435 | 0 | 0 | **-95** | 0 | -95 (tú debes) |  · a favor deudor 145 · a favor tuyo 50 | nivel-max |
| `ARMI` | debe 100 → R doy 50 → M debe 190 → I debo 340 | 290 | 290 | **+0** | 290 | +0 (al día) | — | nivel-max |
| `ARMM` | debe 100 → R doy 50 → M debe 190 → M debe 425 | 715 | 0 | **+765** | 0 | +765 (te deben) | n1 100, n3 190, n4 425 · a favor tuyo 50 | nivel-max |
| `ARMN` | debe 100 → R doy 50 → M debe 190 → N debo 200 | 290 | 150 | **+140** | 150 | +140 (te deben) | n3 140⅟ | nivel-max |
| `ARMR` | debe 100 → R doy 50 → M debe 190 → R doy 50 | 290 | 0 | **+390** | 0 | +390 (te deben) | n1 100, n3 190 · a favor tuyo 100 | nivel-max |
| `ARMS` | debe 100 → R doy 50 → M debe 190 → S debo 510 | 290 | 460 | **-170** | 290 | -170 (tú debes) | n4 170⅟ | nivel-max |
| `ARNE` | debe 100 → R doy 50 → N debo 90 → E recibido 100 | 0 | 40 | **-40** | 0 | -40 (tú debes) | n3 40⅟ | nivel-max |
| `ARNF` | debe 100 → R doy 50 → N debo 90 → F recibido 60 | 40 | 40 | **+0** | 40 | +0 (al día) | — | nivel-max |
| `ARNG` | debe 100 → R doy 50 → N debo 90 → G recibido 150 | 0 | 40 | **-90** | 0 | -90 (tú debes) | n3 40⅟ · a favor deudor 50 | nivel-max |
| `ARNI` | debe 100 → R doy 50 → N debo 90 → I debo 60 | 100 | 100 | **+0** | 100 | +0 (al día) | — | nivel-max |
| `ARNM` | debe 100 → R doy 50 → N debo 90 → M debe 75 | 175 | 40 | **+135** | 40 | +135 (te deben) | n1 60⅟, n4 75 | nivel-max |
| `ARNN` | debe 100 → R doy 50 → N debo 90 → N debo 35 | 100 | 75 | **+25** | 75 | +25 (te deben) | n1 25⅟ | nivel-max |
| `ARNP` | debe 100 → R doy 50 → N debo 90 → P doy 40 | 100 | 0 | **+100** | 0 | +100 (te deben) | n1 100 | nivel-max |
| `ARNQ` | debe 100 → R doy 50 → N debo 90 → Q doy 20 | 100 | 20 | **+80** | 20 | +80 (te deben) | n1 80⅟ | nivel-max |
| `ARNR` | debe 100 → R doy 50 → N debo 90 → R doy 60 | 100 | 0 | **+120** | 0 | +120 (te deben) | n1 100 · a favor tuyo 20 | nivel-max |
| `ARNS` | debe 100 → R doy 50 → N debo 90 → S debo 90 | 100 | 130 | **-30** | 100 | -30 (tú debes) | n4 30⅟ | nivel-max |
| `ARSE` | debe 100 → R doy 50 → S debo 225 → E recibido 100 | 0 | 175 | **-175** | 0 | -175 (tú debes) | n3 175⅟ | nivel-max |
| `ARSF` | debe 100 → R doy 50 → S debo 225 → F recibido 60 | 40 | 175 | **-135** | 40 | -135 (tú debes) | n3 135⅟ | nivel-max |
| `ARSG` | debe 100 → R doy 50 → S debo 225 → G recibido 150 | 0 | 175 | **-225** | 0 | -225 (tú debes) | n3 175⅟ · a favor deudor 50 | nivel-max |
| `ARSI` | debe 100 → R doy 50 → S debo 225 → I debe 75 | 175 | 175 | **+0** | 175 | +0 (al día) | — | nivel-max |
| `ARSM` | debe 100 → R doy 50 → S debo 225 → M debo 95 | 100 | 270 | **-170** | 100 | -170 (tú debes) | n3 75⅟, n4 95 | nivel-max |
| `ARSN` | debe 100 → R doy 50 → S debo 225 → N debe 45 | 145 | 175 | **-30** | 145 | -30 (tú debes) | n3 30⅟ | nivel-max |
| `ARSP` | debe 100 → R doy 50 → S debo 225 → P doy 175 | 100 | 0 | **+100** | 0 | +100 (te deben) | n1 100 | nivel-max |
| `ARSQ` | debe 100 → R doy 50 → S debo 225 → Q doy 105 | 100 | 70 | **+30** | 70 | +30 (te deben) | n1 30⅟ | nivel-max |
| `ARSR` | debe 100 → R doy 50 → S debo 225 → R doy 265 | 100 | 0 | **+190** | 0 | +190 (te deben) | n1 100 · a favor tuyo 90 | nivel-max |
| `ARSS` | debe 100 → R doy 50 → S debo 225 → S debe 115 | 215 | 175 | **+40** | 175 | +40 (te deben) | n4 40⅟ | nivel-max |
| `ASEG` | debe 100 → S debo 150 → E recibido 100 → G recibido 50 | 0 | 150 | **-200** | 0 | -200 (tú debes) | n2 150 · a favor deudor 50 | nivel-max |
| `ASEI` | debe 100 → S debo 150 → E recibido 100 → I debe 150 | 150 | 150 | **+0** | 150 | +0 (al día) | — | nivel-max |
| `ASEM` | debe 100 → S debo 150 → E recibido 100 → M debo 190 | 0 | 340 | **-340** | 0 | -340 (tú debes) | n2 150, n4 190 | nivel-max |
| `ASEN` | debe 100 → S debo 150 → E recibido 100 → N debe 90 | 90 | 150 | **-60** | 90 | -60 (tú debes) | n2 60⅟ | nivel-max |
| `ASEP` | debe 100 → S debo 150 → E recibido 100 → P doy 150 | 0 | 0 | **+0** | 0 | +0 (al día) | — | nivel-max |
| `ASEQ` | debe 100 → S debo 150 → E recibido 100 → Q doy 90 | 0 | 60 | **-60** | 0 | -60 (tú debes) | n2 60⅟ | nivel-max |
| `ASER` | debe 100 → S debo 150 → E recibido 100 → R doy 225 | 0 | 0 | **+75** | 0 | +75 (te deben) |  · a favor tuyo 75 | nivel-max |
| `ASES` | debe 100 → S debo 150 → E recibido 100 → S debe 225 | 225 | 150 | **+75** | 150 | +75 (te deben) | n4 75⅟ | nivel-max |
| `ASFE` | debe 100 → S debo 150 → F recibido 60 → E recibido 40 | 0 | 150 | **-150** | 0 | -150 (tú debes) | n2 150 | nivel-max |
| `ASFF` | debe 100 → S debo 150 → F recibido 60 → F recibido 20 | 20 | 150 | **-130** | 20 | -130 (tú debes) | n2 130⅟ | nivel-max |
| `ASFG` | debe 100 → S debo 150 → F recibido 60 → G recibido 60 | 0 | 150 | **-170** | 0 | -170 (tú debes) | n2 150 · a favor deudor 20 | nivel-max |
| `ASFI` | debe 100 → S debo 150 → F recibido 60 → I debe 110 | 150 | 150 | **+0** | 150 | +0 (al día) | — | nivel-max |
| `ASFM` | debe 100 → S debo 150 → F recibido 60 → M debo 140 | 40 | 290 | **-250** | 40 | -250 (tú debes) | n2 110⅟, n4 140 | nivel-max |
| `ASFN` | debe 100 → S debo 150 → F recibido 60 → N debe 65 | 105 | 150 | **-45** | 105 | -45 (tú debes) | n2 45⅟ | nivel-max |
| `ASFP` | debe 100 → S debo 150 → F recibido 60 → P doy 150 | 40 | 0 | **+40** | 0 | +40 (te deben) | n1 40⅟ | nivel-max |
| `ASFQ` | debe 100 → S debo 150 → F recibido 60 → Q doy 90 | 40 | 60 | **-20** | 40 | -20 (tú debes) | n2 20⅟ | nivel-max |
| `ASFR` | debe 100 → S debo 150 → F recibido 60 → R doy 225 | 40 | 0 | **+115** | 0 | +115 (te deben) | n1 40⅟ · a favor tuyo 75 | nivel-max |
| `ASFS` | debe 100 → S debo 150 → F recibido 60 → S debe 165 | 205 | 150 | **+55** | 150 | +55 (te deben) | n4 55⅟ | nivel-max |
| `ASGG` | debe 100 → S debo 150 → G recibido 150 → G recibido 50 | 0 | 150 | **-250** | 0 | -250 (tú debes) | n2 150 · a favor deudor 100 | nivel-max |
| `ASGI` | debe 100 → S debo 150 → G recibido 150 → I debe 200 | 150 | 150 | **+0** | 150 | +0 (al día) | — | nivel-max |
| `ASGM` | debe 100 → S debo 150 → G recibido 150 → M debo 250 | 0 | 400 | **-450** | 0 | -450 (tú debes) | n2 150, n4 250 · a favor deudor 50 | nivel-max |
| `ASGN` | debe 100 → S debo 150 → G recibido 150 → N debe 120 | 70 | 150 | **-80** | 70 | -80 (tú debes) | n2 80⅟ | nivel-max |
| `ASGP` | debe 100 → S debo 150 → G recibido 150 → P doy 150 | 0 | 0 | **-50** | 0 | -50 (tú debes) |  · a favor deudor 50 | nivel-max |
| `ASGQ` | debe 100 → S debo 150 → G recibido 150 → Q doy 90 | 0 | 60 | **-110** | 0 | -110 (tú debes) | n2 60⅟ · a favor deudor 50 | nivel-max |
| `ASGR` | debe 100 → S debo 150 → G recibido 150 → R doy 225 | 0 | 0 | **+25** | 0 | +25 (te deben) |  · a favor deudor 50 · a favor tuyo 75 | nivel-max |
| `ASGS` | debe 100 → S debo 150 → G recibido 150 → S debe 300 | 250 | 150 | **+100** | 150 | +100 (te deben) | n4 100⅟ | nivel-max |
| `ASIE` | debe 100 → S debo 150 → I debe 50 → E recibido 150 | 0 | 150 | **-150** | 0 | -150 (tú debes) | n2 150 | nivel-max |
| `ASIF` | debe 100 → S debo 150 → I debe 50 → F recibido 90 | 60 | 150 | **-90** | 60 | -90 (tú debes) | n2 90⅟ | nivel-max |
| `ASIG` | debe 100 → S debo 150 → I debe 50 → G recibido 225 | 0 | 150 | **-225** | 0 | -225 (tú debes) | n2 150 · a favor deudor 75 | nivel-max |
| `ASIP` | debe 100 → S debo 150 → I debe 50 → P doy 150 | 150 | 0 | **+150** | 0 | +150 (te deben) | n1 100, n3 50 | nivel-max |
| `ASIQ` | debe 100 → S debo 150 → I debe 50 → Q doy 90 | 150 | 60 | **+90** | 60 | +90 (te deben) | n1 40⅟, n3 50 | nivel-max |
| `ASIR` | debe 100 → S debo 150 → I debe 50 → R doy 225 | 150 | 0 | **+225** | 0 | +225 (te deben) | n1 100, n3 50 · a favor tuyo 75 | nivel-max |
| `ASIX` | debe 100 → S debo 150 → I debe 50 → X debe 75 | 225 | 150 | **+75** | 150 | +75 (te deben) | n4 75 | nivel-max |
| `ASIY` | debe 100 → S debo 150 → I debe 50 → Y debo 75 | 150 | 225 | **-75** | 150 | -75 (tú debes) | n4 75 | nivel-max |
| `ASME` | debe 100 → S debo 150 → M debo 60 → E recibido 100 | 0 | 210 | **-210** | 0 | -210 (tú debes) | n2 150, n3 60 | nivel-max |
| `ASMF` | debe 100 → S debo 150 → M debo 60 → F recibido 60 | 40 | 210 | **-170** | 40 | -170 (tú debes) | n2 110⅟, n3 60 | nivel-max |
| `ASMG` | debe 100 → S debo 150 → M debo 60 → G recibido 150 | 0 | 210 | **-260** | 0 | -260 (tú debes) | n2 150, n3 60 · a favor deudor 50 | nivel-max |
| `ASMI` | debe 100 → S debo 150 → M debo 60 → I debe 110 | 210 | 210 | **+0** | 210 | +0 (al día) | — | nivel-max |
| `ASMM` | debe 100 → S debo 150 → M debo 60 → M debo 140 | 100 | 350 | **-250** | 100 | -250 (tú debes) | n2 50⅟, n3 60, n4 140 | nivel-max |
| `ASMN` | debe 100 → S debo 150 → M debo 60 → N debe 65 | 165 | 210 | **-45** | 165 | -45 (tú debes) | n3 45⅟ | nivel-max |
| `ASMP` | debe 100 → S debo 150 → M debo 60 → P doy 210 | 100 | 0 | **+100** | 0 | +100 (te deben) | n1 100 | nivel-max |
| `ASMQ` | debe 100 → S debo 150 → M debo 60 → Q doy 125 | 100 | 85 | **+15** | 85 | +15 (te deben) | n1 15⅟ | nivel-max |
| `ASMR` | debe 100 → S debo 150 → M debo 60 → R doy 315 | 100 | 0 | **+205** | 0 | +205 (te deben) | n1 100 · a favor tuyo 105 | nivel-max |
| `ASMS` | debe 100 → S debo 150 → M debo 60 → S debe 165 | 265 | 210 | **+55** | 210 | +55 (te deben) | n4 55⅟ | nivel-max |
| `ASNE` | debe 100 → S debo 150 → N debe 30 → E recibido 130 | 0 | 150 | **-150** | 0 | -150 (tú debes) | n2 150 | nivel-max |
| `ASNF` | debe 100 → S debo 150 → N debe 30 → F recibido 75 | 55 | 150 | **-95** | 55 | -95 (tú debes) | n2 95⅟ | nivel-max |
| `ASNG` | debe 100 → S debo 150 → N debe 30 → G recibido 195 | 0 | 150 | **-215** | 0 | -215 (tú debes) | n2 150 · a favor deudor 65 | nivel-max |
| `ASNI` | debe 100 → S debo 150 → N debe 30 → I debe 20 | 150 | 150 | **+0** | 150 | +0 (al día) | — | nivel-max |
| `ASNM` | debe 100 → S debo 150 → N debe 30 → M debo 25 | 130 | 175 | **-45** | 130 | -45 (tú debes) | n2 20⅟, n4 25 | nivel-max |
| `ASNN` | debe 100 → S debo 150 → N debe 30 → N debe 10 | 140 | 150 | **-10** | 140 | -10 (tú debes) | n2 10⅟ | nivel-max |
| `ASNP` | debe 100 → S debo 150 → N debe 30 → P doy 150 | 130 | 0 | **+130** | 0 | +130 (te deben) | n1 100, n3 30 | nivel-max |
| `ASNQ` | debe 100 → S debo 150 → N debe 30 → Q doy 90 | 130 | 60 | **+70** | 60 | +70 (te deben) | n1 40⅟, n3 30 | nivel-max |
| `ASNR` | debe 100 → S debo 150 → N debe 30 → R doy 225 | 130 | 0 | **+205** | 0 | +205 (te deben) | n1 100, n3 30 · a favor tuyo 75 | nivel-max |
| `ASNS` | debe 100 → S debo 150 → N debe 30 → S debe 30 | 160 | 150 | **+10** | 150 | +10 (te deben) | n4 10⅟ | nivel-max |
| `ASPE` | debe 100 → S debo 150 → P doy 150 → E recibido 100 | 0 | 0 | **+0** | 0 | +0 (al día) | — | nivel-max |
| `ASPF` | debe 100 → S debo 150 → P doy 150 → F recibido 60 | 40 | 0 | **+40** | 0 | +40 (te deben) | n1 40⅟ | nivel-max |
| `ASPG` | debe 100 → S debo 150 → P doy 150 → G recibido 150 | 0 | 0 | **-50** | 0 | -50 (tú debes) |  · a favor deudor 50 | nivel-max |
| `ASPI` | debe 100 → S debo 150 → P doy 150 → I debo 100 | 100 | 100 | **+0** | 100 | +0 (al día) | — | nivel-max |
| `ASPM` | debe 100 → S debo 150 → P doy 150 → M debe 125 | 225 | 0 | **+225** | 0 | +225 (te deben) | n1 100, n4 125 | nivel-max |
| `ASPN` | debe 100 → S debo 150 → P doy 150 → N debo 60 | 100 | 60 | **+40** | 60 | +40 (te deben) | n1 40⅟ | nivel-max |
| `ASPR` | debe 100 → S debo 150 → P doy 150 → R doy 50 | 100 | 0 | **+150** | 0 | +150 (te deben) | n1 100 · a favor tuyo 50 | nivel-max |
| `ASPS` | debe 100 → S debo 150 → P doy 150 → S debo 150 | 100 | 150 | **-50** | 100 | -50 (tú debes) | n4 50⅟ | nivel-max |
| `ASQE` | debe 100 → S debo 150 → Q doy 90 → E recibido 100 | 0 | 60 | **-60** | 0 | -60 (tú debes) | n2 60⅟ | nivel-max |
| `ASQF` | debe 100 → S debo 150 → Q doy 90 → F recibido 60 | 40 | 60 | **-20** | 40 | -20 (tú debes) | n2 20⅟ | nivel-max |
| `ASQG` | debe 100 → S debo 150 → Q doy 90 → G recibido 150 | 0 | 60 | **-110** | 0 | -110 (tú debes) | n2 60⅟ · a favor deudor 50 | nivel-max |
| `ASQI` | debe 100 → S debo 150 → Q doy 90 → I debo 40 | 100 | 100 | **+0** | 100 | +0 (al día) | — | nivel-max |
| `ASQM` | debe 100 → S debo 150 → Q doy 90 → M debe 50 | 150 | 60 | **+90** | 60 | +90 (te deben) | n1 40⅟, n4 50 | nivel-max |
| `ASQN` | debe 100 → S debo 150 → Q doy 90 → N debo 20 | 100 | 80 | **+20** | 80 | +20 (te deben) | n1 20⅟ | nivel-max |
| `ASQP` | debe 100 → S debo 150 → Q doy 90 → P doy 60 | 100 | 0 | **+100** | 0 | +100 (te deben) | n1 100 | nivel-max |
| `ASQQ` | debe 100 → S debo 150 → Q doy 90 → Q doy 35 | 100 | 25 | **+75** | 25 | +75 (te deben) | n1 75⅟ | nivel-max |
| `ASQR` | debe 100 → S debo 150 → Q doy 90 → R doy 90 | 100 | 0 | **+130** | 0 | +130 (te deben) | n1 100 · a favor tuyo 30 | nivel-max |
| `ASQS` | debe 100 → S debo 150 → Q doy 90 → S debo 60 | 100 | 120 | **-20** | 100 | -20 (tú debes) | n4 20⅟ | nivel-max |
| `ASRE` | debe 100 → S debo 150 → R doy 225 → E recibido 100 | 0 | 0 | **+75** | 0 | +75 (te deben) |  · a favor tuyo 75 | nivel-max |
| `ASRF` | debe 100 → S debo 150 → R doy 225 → F recibido 60 | 40 | 0 | **+115** | 0 | +115 (te deben) | n1 40⅟ · a favor tuyo 75 | nivel-max |
| `ASRG` | debe 100 → S debo 150 → R doy 225 → G recibido 150 | 0 | 0 | **+25** | 0 | +25 (te deben) |  · a favor deudor 50 · a favor tuyo 75 | nivel-max |
| `ASRI` | debe 100 → S debo 150 → R doy 225 → I debo 175 | 100 | 100 | **+0** | 100 | +0 (al día) | — | nivel-max |
| `ASRM` | debe 100 → S debo 150 → R doy 225 → M debe 220 | 320 | 0 | **+395** | 0 | +395 (te deben) | n1 100, n4 220 · a favor tuyo 75 | nivel-max |
| `ASRN` | debe 100 → S debo 150 → R doy 225 → N debo 105 | 100 | 30 | **+70** | 30 | +70 (te deben) | n1 70⅟ | nivel-max |
| `ASRR` | debe 100 → S debo 150 → R doy 225 → R doy 50 | 100 | 0 | **+225** | 0 | +225 (te deben) | n1 100 · a favor tuyo 125 | nivel-max |
| `ASRS` | debe 100 → S debo 150 → R doy 225 → S debo 265 | 100 | 190 | **-90** | 100 | -90 (tú debes) | n4 90⅟ | nivel-max |
| `BGIE` | debo 100 → G recibido 50 → I debe 150 → E recibido 100 | 0 | 100 | **-100** | 0 | -100 (tú debes) | n1 100 | nivel-max |
| `BGIF` | debo 100 → G recibido 50 → I debe 150 → F recibido 60 | 40 | 100 | **-60** | 40 | -60 (tú debes) | n1 60⅟ | nivel-max |
| `BGIG` | debo 100 → G recibido 50 → I debe 150 → G recibido 150 | 0 | 100 | **-150** | 0 | -150 (tú debes) | n1 100 · a favor deudor 50 | nivel-max |
| `BGIP` | debo 100 → G recibido 50 → I debe 150 → P doy 100 | 100 | 0 | **+100** | 0 | +100 (te deben) | n3 100⅟ | nivel-max |
| `BGIQ` | debo 100 → G recibido 50 → I debe 150 → Q doy 60 | 100 | 40 | **+60** | 40 | +60 (te deben) | n3 60⅟ | nivel-max |
| `BGIR` | debo 100 → G recibido 50 → I debe 150 → R doy 150 | 100 | 0 | **+150** | 0 | +150 (te deben) | n3 100⅟ · a favor tuyo 50 | nivel-max |
| `BGIX` | debo 100 → G recibido 50 → I debe 150 → X debe 75 | 175 | 100 | **+75** | 100 | +75 (te deben) | n4 75 | nivel-max |
| `BGIY` | debo 100 → G recibido 50 → I debe 150 → Y debo 75 | 100 | 175 | **-75** | 100 | -75 (tú debes) | n4 75 | nivel-max |
| `BGMG` | debo 100 → G recibido 50 → M debo 190 → G recibido 50 | 0 | 290 | **-390** | 0 | -390 (tú debes) | n1 100, n3 190 · a favor deudor 100 | nivel-max |
| `BGMI` | debo 100 → G recibido 50 → M debo 190 → I debe 340 | 290 | 290 | **+0** | 290 | +0 (al día) | — | nivel-max |
| `BGMM` | debo 100 → G recibido 50 → M debo 190 → M debo 425 | 0 | 715 | **-765** | 0 | -765 (tú debes) | n1 100, n3 190, n4 425 · a favor deudor 50 | nivel-max |
| `BGMN` | debo 100 → G recibido 50 → M debo 190 → N debe 200 | 150 | 290 | **-140** | 150 | -140 (tú debes) | n3 140⅟ | nivel-max |
| `BGMP` | debo 100 → G recibido 50 → M debo 190 → P doy 290 | 0 | 0 | **-50** | 0 | -50 (tú debes) |  · a favor deudor 50 | nivel-max |
| `BGMQ` | debo 100 → G recibido 50 → M debo 190 → Q doy 170 | 0 | 120 | **-170** | 0 | -170 (tú debes) | n3 120⅟ · a favor deudor 50 | nivel-max |
| `BGMR` | debo 100 → G recibido 50 → M debo 190 → R doy 435 | 0 | 0 | **+95** | 0 | +95 (te deben) |  · a favor deudor 50 · a favor tuyo 145 | nivel-max |
| `BGMS` | debo 100 → G recibido 50 → M debo 190 → S debe 510 | 460 | 290 | **+170** | 290 | +170 (te deben) | n4 170⅟ | nivel-max |
| `BGNE` | debo 100 → G recibido 50 → N debe 90 → E recibido 40 | 0 | 100 | **-100** | 0 | -100 (tú debes) | n1 100 | nivel-max |
| `BGNF` | debo 100 → G recibido 50 → N debe 90 → F recibido 20 | 20 | 100 | **-80** | 20 | -80 (tú debes) | n1 80⅟ | nivel-max |
| `BGNG` | debo 100 → G recibido 50 → N debe 90 → G recibido 60 | 0 | 100 | **-120** | 0 | -120 (tú debes) | n1 100 · a favor deudor 20 | nivel-max |
| `BGNI` | debo 100 → G recibido 50 → N debe 90 → I debe 60 | 100 | 100 | **+0** | 100 | +0 (al día) | — | nivel-max |
| `BGNM` | debo 100 → G recibido 50 → N debe 90 → M debo 75 | 40 | 175 | **-135** | 40 | -135 (tú debes) | n1 60⅟, n4 75 | nivel-max |
| `BGNN` | debo 100 → G recibido 50 → N debe 90 → N debe 35 | 75 | 100 | **-25** | 75 | -25 (tú debes) | n1 25⅟ | nivel-max |
| `BGNP` | debo 100 → G recibido 50 → N debe 90 → P doy 100 | 40 | 0 | **+40** | 0 | +40 (te deben) | n3 40⅟ | nivel-max |
| `BGNQ` | debo 100 → G recibido 50 → N debe 90 → Q doy 60 | 40 | 40 | **+0** | 40 | +0 (al día) | — | nivel-max |
| `BGNR` | debo 100 → G recibido 50 → N debe 90 → R doy 150 | 40 | 0 | **+90** | 0 | +90 (te deben) | n3 40⅟ · a favor tuyo 50 | nivel-max |
| `BGNS` | debo 100 → G recibido 50 → N debe 90 → S debe 90 | 130 | 100 | **+30** | 100 | +30 (te deben) | n4 30⅟ | nivel-max |
| `BGPG` | debo 100 → G recibido 50 → P doy 100 → G recibido 50 | 0 | 0 | **-100** | 0 | -100 (tú debes) |  · a favor deudor 100 | nivel-max |
| `BGPI` | debo 100 → G recibido 50 → P doy 100 → I debe 50 | 0 | 0 | **+0** | 0 | +0 (al día) | — | nivel-max |
| `BGPM` | debo 100 → G recibido 50 → P doy 100 → M debo 60 | 0 | 60 | **-110** | 0 | -110 (tú debes) | n4 60 · a favor deudor 50 | nivel-max |
| `BGPN` | debo 100 → G recibido 50 → P doy 100 → N debe 30 | 0 | 0 | **-20** | 0 | -20 (tú debes) |  · a favor deudor 20 | nivel-max |
| `BGPR` | debo 100 → G recibido 50 → P doy 100 → R doy 50 | 0 | 0 | **+0** | 0 | +0 (al día) |  · a favor deudor 50 · a favor tuyo 50 | nivel-max |
| `BGPS` | debo 100 → G recibido 50 → P doy 100 → S debe 75 | 25 | 0 | **+25** | 0 | +25 (te deben) | n4 25⅟ | nivel-max |
| `BGQG` | debo 100 → G recibido 50 → Q doy 60 → G recibido 50 | 0 | 40 | **-140** | 0 | -140 (tú debes) | n1 40⅟ · a favor deudor 100 | nivel-max |
| `BGQI` | debo 100 → G recibido 50 → Q doy 60 → I debe 90 | 40 | 40 | **+0** | 40 | +0 (al día) | — | nivel-max |
| `BGQM` | debo 100 → G recibido 50 → Q doy 60 → M debo 110 | 0 | 150 | **-200** | 0 | -200 (tú debes) | n1 40⅟, n4 110 · a favor deudor 50 | nivel-max |
| `BGQN` | debo 100 → G recibido 50 → Q doy 60 → N debe 50 | 0 | 40 | **-40** | 0 | -40 (tú debes) | n1 40⅟ | nivel-max |
| `BGQP` | debo 100 → G recibido 50 → Q doy 60 → P doy 40 | 0 | 0 | **-50** | 0 | -50 (tú debes) |  · a favor deudor 50 | nivel-max |
| `BGQQ` | debo 100 → G recibido 50 → Q doy 60 → Q doy 20 | 0 | 20 | **-70** | 0 | -70 (tú debes) | n1 20⅟ · a favor deudor 50 | nivel-max |
| `BGQR` | debo 100 → G recibido 50 → Q doy 60 → R doy 60 | 0 | 0 | **-30** | 0 | -30 (tú debes) |  · a favor deudor 50 · a favor tuyo 20 | nivel-max |
| `BGQS` | debo 100 → G recibido 50 → Q doy 60 → S debe 135 | 85 | 40 | **+45** | 40 | +45 (te deben) | n4 45⅟ | nivel-max |
| `BGRG` | debo 100 → G recibido 50 → R doy 150 → G recibido 50 | 0 | 0 | **-50** | 0 | -50 (tú debes) |  · a favor deudor 100 · a favor tuyo 50 | nivel-max |
| `BGRR` | debo 100 → G recibido 50 → R doy 150 → R doy 50 | 0 | 0 | **+50** | 0 | +50 (te deben) |  · a favor deudor 50 · a favor tuyo 100 | nivel-max |
| `BGRX` | debo 100 → G recibido 50 → R doy 150 → X debe 50 | 0 | 0 | **+50** | 0 | +50 (te deben) |  · a favor tuyo 50 | nivel-max |
| `BGRY` | debo 100 → G recibido 50 → R doy 150 → Y debo 50 | 0 | 0 | **-50** | 0 | -50 (tú debes) |  · a favor deudor 50 | nivel-max |
| `BGSE` | debo 100 → G recibido 50 → S debe 225 → E recibido 175 | 0 | 100 | **-100** | 0 | -100 (tú debes) | n1 100 | nivel-max |
| `BGSF` | debo 100 → G recibido 50 → S debe 225 → F recibido 105 | 70 | 100 | **-30** | 70 | -30 (tú debes) | n1 30⅟ | nivel-max |
| `BGSG` | debo 100 → G recibido 50 → S debe 225 → G recibido 265 | 0 | 100 | **-190** | 0 | -190 (tú debes) | n1 100 · a favor deudor 90 | nivel-max |
| `BGSI` | debo 100 → G recibido 50 → S debe 225 → I debo 75 | 175 | 175 | **+0** | 175 | +0 (al día) | — | nivel-max |
| `BGSM` | debo 100 → G recibido 50 → S debe 225 → M debe 95 | 270 | 100 | **+170** | 100 | +170 (te deben) | n3 75⅟, n4 95 | nivel-max |
| `BGSN` | debo 100 → G recibido 50 → S debe 225 → N debo 45 | 175 | 145 | **+30** | 145 | +30 (te deben) | n3 30⅟ | nivel-max |
| `BGSP` | debo 100 → G recibido 50 → S debe 225 → P doy 100 | 175 | 0 | **+175** | 0 | +175 (te deben) | n3 175⅟ | nivel-max |
| `BGSQ` | debo 100 → G recibido 50 → S debe 225 → Q doy 60 | 175 | 40 | **+135** | 40 | +135 (te deben) | n3 135⅟ | nivel-max |
| `BGSR` | debo 100 → G recibido 50 → S debe 225 → R doy 150 | 175 | 0 | **+225** | 0 | +225 (te deben) | n3 175⅟ · a favor tuyo 50 | nivel-max |
| `BGSS` | debo 100 → G recibido 50 → S debe 225 → S debo 115 | 175 | 215 | **-40** | 175 | -40 (tú debes) | n4 40⅟ | nivel-max |
| `BIEG` | debo 100 → I debe 100 → E recibido 100 → G recibido 50 | 0 | 100 | **-150** | 0 | -150 (tú debes) | n1 100 · a favor deudor 50 | nivel-max |
| `BIEI` | debo 100 → I debe 100 → E recibido 100 → I debe 100 | 100 | 100 | **+0** | 100 | +0 (al día) | — | nivel-max |
| `BIEM` | debo 100 → I debe 100 → E recibido 100 → M debo 125 | 0 | 225 | **-225** | 0 | -225 (tú debes) | n1 100, n4 125 | nivel-max |
| `BIEN` | debo 100 → I debe 100 → E recibido 100 → N debe 60 | 60 | 100 | **-40** | 60 | -40 (tú debes) | n1 40⅟ | nivel-max |
| `BIEP` | debo 100 → I debe 100 → E recibido 100 → P doy 100 | 0 | 0 | **+0** | 0 | +0 (al día) | — | nivel-max |
| `BIEQ` | debo 100 → I debe 100 → E recibido 100 → Q doy 60 | 0 | 40 | **-40** | 0 | -40 (tú debes) | n1 40⅟ | nivel-max |
| `BIER` | debo 100 → I debe 100 → E recibido 100 → R doy 150 | 0 | 0 | **+50** | 0 | +50 (te deben) |  · a favor tuyo 50 | nivel-max |
| `BIES` | debo 100 → I debe 100 → E recibido 100 → S debe 150 | 150 | 100 | **+50** | 100 | +50 (te deben) | n4 50⅟ | nivel-max |
| `BIFE` | debo 100 → I debe 100 → F recibido 60 → E recibido 40 | 0 | 100 | **-100** | 0 | -100 (tú debes) | n1 100 | nivel-max |
| `BIFF` | debo 100 → I debe 100 → F recibido 60 → F recibido 20 | 20 | 100 | **-80** | 20 | -80 (tú debes) | n1 80⅟ | nivel-max |
| `BIFG` | debo 100 → I debe 100 → F recibido 60 → G recibido 60 | 0 | 100 | **-120** | 0 | -120 (tú debes) | n1 100 · a favor deudor 20 | nivel-max |
| `BIFI` | debo 100 → I debe 100 → F recibido 60 → I debe 60 | 100 | 100 | **+0** | 100 | +0 (al día) | — | nivel-max |
| `BIFM` | debo 100 → I debe 100 → F recibido 60 → M debo 75 | 40 | 175 | **-135** | 40 | -135 (tú debes) | n1 60⅟, n4 75 | nivel-max |
| `BIFN` | debo 100 → I debe 100 → F recibido 60 → N debe 35 | 75 | 100 | **-25** | 75 | -25 (tú debes) | n1 25⅟ | nivel-max |
| `BIFP` | debo 100 → I debe 100 → F recibido 60 → P doy 100 | 40 | 0 | **+40** | 0 | +40 (te deben) | n2 40⅟ | nivel-max |
| `BIFQ` | debo 100 → I debe 100 → F recibido 60 → Q doy 60 | 40 | 40 | **+0** | 40 | +0 (al día) | — | nivel-max |
| `BIFR` | debo 100 → I debe 100 → F recibido 60 → R doy 150 | 40 | 0 | **+90** | 0 | +90 (te deben) | n2 40⅟ · a favor tuyo 50 | nivel-max |
| `BIFS` | debo 100 → I debe 100 → F recibido 60 → S debe 90 | 130 | 100 | **+30** | 100 | +30 (te deben) | n4 30⅟ | nivel-max |
| `BIGG` | debo 100 → I debe 100 → G recibido 150 → G recibido 50 | 0 | 100 | **-200** | 0 | -200 (tú debes) | n1 100 · a favor deudor 100 | nivel-max |
| `BIGI` | debo 100 → I debe 100 → G recibido 150 → I debe 150 | 100 | 100 | **+0** | 100 | +0 (al día) | — | nivel-max |
| `BIGM` | debo 100 → I debe 100 → G recibido 150 → M debo 190 | 0 | 290 | **-340** | 0 | -340 (tú debes) | n1 100, n4 190 · a favor deudor 50 | nivel-max |
| `BIGN` | debo 100 → I debe 100 → G recibido 150 → N debe 90 | 40 | 100 | **-60** | 40 | -60 (tú debes) | n1 60⅟ | nivel-max |
| `BIGP` | debo 100 → I debe 100 → G recibido 150 → P doy 100 | 0 | 0 | **-50** | 0 | -50 (tú debes) |  · a favor deudor 50 | nivel-max |
| `BIGQ` | debo 100 → I debe 100 → G recibido 150 → Q doy 60 | 0 | 40 | **-90** | 0 | -90 (tú debes) | n1 40⅟ · a favor deudor 50 | nivel-max |
| `BIGR` | debo 100 → I debe 100 → G recibido 150 → R doy 150 | 0 | 0 | **+0** | 0 | +0 (al día) |  · a favor deudor 50 · a favor tuyo 50 | nivel-max |
| `BIGS` | debo 100 → I debe 100 → G recibido 150 → S debe 225 | 175 | 100 | **+75** | 100 | +75 (te deben) | n4 75⅟ | nivel-max |
| `BIPE` | debo 100 → I debe 100 → P doy 100 → E recibido 100 | 0 | 0 | **+0** | 0 | +0 (al día) | — | nivel-max |
| `BIPF` | debo 100 → I debe 100 → P doy 100 → F recibido 60 | 40 | 0 | **+40** | 0 | +40 (te deben) | n2 40⅟ | nivel-max |
| `BIPG` | debo 100 → I debe 100 → P doy 100 → G recibido 150 | 0 | 0 | **-50** | 0 | -50 (tú debes) |  · a favor deudor 50 | nivel-max |
| `BIPI` | debo 100 → I debe 100 → P doy 100 → I debo 100 | 100 | 100 | **+0** | 100 | +0 (al día) | — | nivel-max |
| `BIPM` | debo 100 → I debe 100 → P doy 100 → M debe 125 | 225 | 0 | **+225** | 0 | +225 (te deben) | n2 100, n4 125 | nivel-max |
| `BIPN` | debo 100 → I debe 100 → P doy 100 → N debo 60 | 100 | 60 | **+40** | 60 | +40 (te deben) | n2 40⅟ | nivel-max |
| `BIPR` | debo 100 → I debe 100 → P doy 100 → R doy 50 | 100 | 0 | **+150** | 0 | +150 (te deben) | n2 100 · a favor tuyo 50 | nivel-max |
| `BIPS` | debo 100 → I debe 100 → P doy 100 → S debo 150 | 100 | 150 | **-50** | 100 | -50 (tú debes) | n4 50⅟ | nivel-max |
| `BIQE` | debo 100 → I debe 100 → Q doy 60 → E recibido 100 | 0 | 40 | **-40** | 0 | -40 (tú debes) | n1 40⅟ | nivel-max |
| `BIQF` | debo 100 → I debe 100 → Q doy 60 → F recibido 60 | 40 | 40 | **+0** | 40 | +0 (al día) | — | nivel-max |
| `BIQG` | debo 100 → I debe 100 → Q doy 60 → G recibido 150 | 0 | 40 | **-90** | 0 | -90 (tú debes) | n1 40⅟ · a favor deudor 50 | nivel-max |
| `BIQI` | debo 100 → I debe 100 → Q doy 60 → I debo 60 | 100 | 100 | **+0** | 100 | +0 (al día) | — | nivel-max |
| `BIQM` | debo 100 → I debe 100 → Q doy 60 → M debe 75 | 175 | 40 | **+135** | 40 | +135 (te deben) | n2 60⅟, n4 75 | nivel-max |
| `BIQN` | debo 100 → I debe 100 → Q doy 60 → N debo 35 | 100 | 75 | **+25** | 75 | +25 (te deben) | n2 25⅟ | nivel-max |
| `BIQP` | debo 100 → I debe 100 → Q doy 60 → P doy 40 | 100 | 0 | **+100** | 0 | +100 (te deben) | n2 100 | nivel-max |
| `BIQQ` | debo 100 → I debe 100 → Q doy 60 → Q doy 20 | 100 | 20 | **+80** | 20 | +80 (te deben) | n2 80⅟ | nivel-max |
| `BIQR` | debo 100 → I debe 100 → Q doy 60 → R doy 60 | 100 | 0 | **+120** | 0 | +120 (te deben) | n2 100 · a favor tuyo 20 | nivel-max |
| `BIQS` | debo 100 → I debe 100 → Q doy 60 → S debo 90 | 100 | 130 | **-30** | 100 | -30 (tú debes) | n4 30⅟ | nivel-max |
| `BIRE` | debo 100 → I debe 100 → R doy 150 → E recibido 100 | 0 | 0 | **+50** | 0 | +50 (te deben) |  · a favor tuyo 50 | nivel-max |
| `BIRF` | debo 100 → I debe 100 → R doy 150 → F recibido 60 | 40 | 0 | **+90** | 0 | +90 (te deben) | n2 40⅟ · a favor tuyo 50 | nivel-max |
| `BIRG` | debo 100 → I debe 100 → R doy 150 → G recibido 150 | 0 | 0 | **+0** | 0 | +0 (al día) |  · a favor deudor 50 · a favor tuyo 50 | nivel-max |
| `BIRI` | debo 100 → I debe 100 → R doy 150 → I debo 150 | 100 | 100 | **+0** | 100 | +0 (al día) | — | nivel-max |
| `BIRM` | debo 100 → I debe 100 → R doy 150 → M debe 190 | 290 | 0 | **+340** | 0 | +340 (te deben) | n2 100, n4 190 · a favor tuyo 50 | nivel-max |
| `BIRN` | debo 100 → I debe 100 → R doy 150 → N debo 90 | 100 | 40 | **+60** | 40 | +60 (te deben) | n2 60⅟ | nivel-max |
| `BIRR` | debo 100 → I debe 100 → R doy 150 → R doy 50 | 100 | 0 | **+200** | 0 | +200 (te deben) | n2 100 · a favor tuyo 100 | nivel-max |
| `BIRS` | debo 100 → I debe 100 → R doy 150 → S debo 225 | 100 | 175 | **-75** | 100 | -75 (tú debes) | n4 75⅟ | nivel-max |
| `BIXE` | debo 100 → I debe 100 → X debe 50 → E recibido 150 | 0 | 100 | **-100** | 0 | -100 (tú debes) | n1 100 | nivel-max |
| `BIXF` | debo 100 → I debe 100 → X debe 50 → F recibido 90 | 60 | 100 | **-40** | 60 | -40 (tú debes) | n1 40⅟ | nivel-max |
| `BIXG` | debo 100 → I debe 100 → X debe 50 → G recibido 225 | 0 | 100 | **-175** | 0 | -175 (tú debes) | n1 100 · a favor deudor 75 | nivel-max |
| `BIXI` | debo 100 → I debe 100 → X debe 50 → I debo 50 | 150 | 150 | **+0** | 150 | +0 (al día) | — | nivel-max |
| `BIXM` | debo 100 → I debe 100 → X debe 50 → M debe 60 | 210 | 100 | **+110** | 100 | +110 (te deben) | n3 50, n4 60 | nivel-max |
| `BIXN` | debo 100 → I debe 100 → X debe 50 → N debo 30 | 150 | 130 | **+20** | 130 | +20 (te deben) | n3 20⅟ | nivel-max |
| `BIXP` | debo 100 → I debe 100 → X debe 50 → P doy 100 | 150 | 0 | **+150** | 0 | +150 (te deben) | n2 100, n3 50 | nivel-max |
| `BIXQ` | debo 100 → I debe 100 → X debe 50 → Q doy 60 | 150 | 40 | **+110** | 40 | +110 (te deben) | n2 60⅟, n3 50 | nivel-max |
| `BIXR` | debo 100 → I debe 100 → X debe 50 → R doy 150 | 150 | 0 | **+200** | 0 | +200 (te deben) | n2 100, n3 50 · a favor tuyo 50 | nivel-max |
| `BIXS` | debo 100 → I debe 100 → X debe 50 → S debo 75 | 150 | 175 | **-25** | 150 | -25 (tú debes) | n4 25⅟ | nivel-max |
| `BIYE` | debo 100 → I debe 100 → Y debo 50 → E recibido 100 | 0 | 150 | **-150** | 0 | -150 (tú debes) | n1 100, n3 50 | nivel-max |
| `BIYF` | debo 100 → I debe 100 → Y debo 50 → F recibido 60 | 40 | 150 | **-110** | 40 | -110 (tú debes) | n1 60⅟, n3 50 | nivel-max |
| `BIYG` | debo 100 → I debe 100 → Y debo 50 → G recibido 150 | 0 | 150 | **-200** | 0 | -200 (tú debes) | n1 100, n3 50 · a favor deudor 50 | nivel-max |
| `BIYI` | debo 100 → I debe 100 → Y debo 50 → I debe 50 | 150 | 150 | **+0** | 150 | +0 (al día) | — | nivel-max |
| `BIYM` | debo 100 → I debe 100 → Y debo 50 → M debo 60 | 100 | 210 | **-110** | 100 | -110 (tú debes) | n3 50, n4 60 | nivel-max |
| `BIYN` | debo 100 → I debe 100 → Y debo 50 → N debe 30 | 130 | 150 | **-20** | 130 | -20 (tú debes) | n3 20⅟ | nivel-max |
| `BIYP` | debo 100 → I debe 100 → Y debo 50 → P doy 150 | 100 | 0 | **+100** | 0 | +100 (te deben) | n2 100 | nivel-max |
| `BIYQ` | debo 100 → I debe 100 → Y debo 50 → Q doy 90 | 100 | 60 | **+40** | 60 | +40 (te deben) | n2 40⅟ | nivel-max |
| `BIYR` | debo 100 → I debe 100 → Y debo 50 → R doy 225 | 100 | 0 | **+175** | 0 | +175 (te deben) | n2 100 · a favor tuyo 75 | nivel-max |
| `BIYS` | debo 100 → I debe 100 → Y debo 50 → S debe 75 | 175 | 150 | **+25** | 150 | +25 (te deben) | n4 25⅟ | nivel-max |
| `BNEG` | debo 100 → N debe 60 → E recibido 60 → G recibido 50 | 0 | 100 | **-150** | 0 | -150 (tú debes) | n1 100 · a favor deudor 50 | nivel-max |
| `BNEI` | debo 100 → N debe 60 → E recibido 60 → I debe 100 | 100 | 100 | **+0** | 100 | +0 (al día) | — | nivel-max |
| `BNEM` | debo 100 → N debe 60 → E recibido 60 → M debo 125 | 0 | 225 | **-225** | 0 | -225 (tú debes) | n1 100, n4 125 | nivel-max |
| `BNEN` | debo 100 → N debe 60 → E recibido 60 → N debe 60 | 60 | 100 | **-40** | 60 | -40 (tú debes) | n1 40⅟ | nivel-max |
| `BNEP` | debo 100 → N debe 60 → E recibido 60 → P doy 100 | 0 | 0 | **+0** | 0 | +0 (al día) | — | nivel-max |
| `BNEQ` | debo 100 → N debe 60 → E recibido 60 → Q doy 60 | 0 | 40 | **-40** | 0 | -40 (tú debes) | n1 40⅟ | nivel-max |
| `BNER` | debo 100 → N debe 60 → E recibido 60 → R doy 150 | 0 | 0 | **+50** | 0 | +50 (te deben) |  · a favor tuyo 50 | nivel-max |
| `BNES` | debo 100 → N debe 60 → E recibido 60 → S debe 150 | 150 | 100 | **+50** | 100 | +50 (te deben) | n4 50⅟ | nivel-max |
| `BNFE` | debo 100 → N debe 60 → F recibido 35 → E recibido 25 | 0 | 100 | **-100** | 0 | -100 (tú debes) | n1 100 | nivel-max |
| `BNFF` | debo 100 → N debe 60 → F recibido 35 → F recibido 15 | 10 | 100 | **-90** | 10 | -90 (tú debes) | n1 90⅟ | nivel-max |
| `BNFG` | debo 100 → N debe 60 → F recibido 35 → G recibido 40 | 0 | 100 | **-115** | 0 | -115 (tú debes) | n1 100 · a favor deudor 15 | nivel-max |
| `BNFI` | debo 100 → N debe 60 → F recibido 35 → I debe 75 | 100 | 100 | **+0** | 100 | +0 (al día) | — | nivel-max |
| `BNFM` | debo 100 → N debe 60 → F recibido 35 → M debo 95 | 25 | 195 | **-170** | 25 | -170 (tú debes) | n1 75⅟, n4 95 | nivel-max |
| `BNFN` | debo 100 → N debe 60 → F recibido 35 → N debe 45 | 70 | 100 | **-30** | 70 | -30 (tú debes) | n1 30⅟ | nivel-max |
| `BNFP` | debo 100 → N debe 60 → F recibido 35 → P doy 100 | 25 | 0 | **+25** | 0 | +25 (te deben) | n2 25⅟ | nivel-max |
| `BNFQ` | debo 100 → N debe 60 → F recibido 35 → Q doy 60 | 25 | 40 | **-15** | 25 | -15 (tú debes) | n1 15⅟ | nivel-max |
| `BNFR` | debo 100 → N debe 60 → F recibido 35 → R doy 150 | 25 | 0 | **+75** | 0 | +75 (te deben) | n2 25⅟ · a favor tuyo 50 | nivel-max |
| `BNFS` | debo 100 → N debe 60 → F recibido 35 → S debe 115 | 140 | 100 | **+40** | 100 | +40 (te deben) | n4 40⅟ | nivel-max |
| `BNGG` | debo 100 → N debe 60 → G recibido 90 → G recibido 50 | 0 | 100 | **-180** | 0 | -180 (tú debes) | n1 100 · a favor deudor 80 | nivel-max |
| `BNGI` | debo 100 → N debe 60 → G recibido 90 → I debe 130 | 100 | 100 | **+0** | 100 | +0 (al día) | — | nivel-max |
| `BNGM` | debo 100 → N debe 60 → G recibido 90 → M debo 160 | 0 | 260 | **-290** | 0 | -290 (tú debes) | n1 100, n4 160 · a favor deudor 30 | nivel-max |
| `BNGN` | debo 100 → N debe 60 → G recibido 90 → N debe 75 | 45 | 100 | **-55** | 45 | -55 (tú debes) | n1 55⅟ | nivel-max |
| `BNGP` | debo 100 → N debe 60 → G recibido 90 → P doy 100 | 0 | 0 | **-30** | 0 | -30 (tú debes) |  · a favor deudor 30 | nivel-max |
| `BNGQ` | debo 100 → N debe 60 → G recibido 90 → Q doy 60 | 0 | 40 | **-70** | 0 | -70 (tú debes) | n1 40⅟ · a favor deudor 30 | nivel-max |
| `BNGR` | debo 100 → N debe 60 → G recibido 90 → R doy 150 | 0 | 0 | **+20** | 0 | +20 (te deben) |  · a favor deudor 30 · a favor tuyo 50 | nivel-max |
| `BNGS` | debo 100 → N debe 60 → G recibido 90 → S debe 195 | 165 | 100 | **+65** | 100 | +65 (te deben) | n4 65⅟ | nivel-max |
| `BNIE` | debo 100 → N debe 60 → I debe 40 → E recibido 100 | 0 | 100 | **-100** | 0 | -100 (tú debes) | n1 100 | nivel-max |
| `BNIF` | debo 100 → N debe 60 → I debe 40 → F recibido 60 | 40 | 100 | **-60** | 40 | -60 (tú debes) | n1 60⅟ | nivel-max |
| `BNIG` | debo 100 → N debe 60 → I debe 40 → G recibido 150 | 0 | 100 | **-150** | 0 | -150 (tú debes) | n1 100 · a favor deudor 50 | nivel-max |
| `BNIP` | debo 100 → N debe 60 → I debe 40 → P doy 100 | 100 | 0 | **+100** | 0 | +100 (te deben) | n2 60, n3 40 | nivel-max |
| `BNIQ` | debo 100 → N debe 60 → I debe 40 → Q doy 60 | 100 | 40 | **+60** | 40 | +60 (te deben) | n2 20⅟, n3 40 | nivel-max |
| `BNIR` | debo 100 → N debe 60 → I debe 40 → R doy 150 | 100 | 0 | **+150** | 0 | +150 (te deben) | n2 60, n3 40 · a favor tuyo 50 | nivel-max |
| `BNIX` | debo 100 → N debe 60 → I debe 40 → X debe 50 | 150 | 100 | **+50** | 100 | +50 (te deben) | n4 50 | nivel-max |
| `BNIY` | debo 100 → N debe 60 → I debe 40 → Y debo 50 | 100 | 150 | **-50** | 100 | -50 (tú debes) | n4 50 | nivel-max |
| `BNME` | debo 100 → N debe 60 → M debo 50 → E recibido 60 | 0 | 150 | **-150** | 0 | -150 (tú debes) | n1 100, n3 50 | nivel-max |
| `BNMF` | debo 100 → N debe 60 → M debo 50 → F recibido 35 | 25 | 150 | **-125** | 25 | -125 (tú debes) | n1 75⅟, n3 50 | nivel-max |
| `BNMG` | debo 100 → N debe 60 → M debo 50 → G recibido 90 | 0 | 150 | **-180** | 0 | -180 (tú debes) | n1 100, n3 50 · a favor deudor 30 | nivel-max |
| `BNMI` | debo 100 → N debe 60 → M debo 50 → I debe 90 | 150 | 150 | **+0** | 150 | +0 (al día) | — | nivel-max |
| `BNMM` | debo 100 → N debe 60 → M debo 50 → M debo 110 | 60 | 260 | **-200** | 60 | -200 (tú debes) | n1 40⅟, n3 50, n4 110 | nivel-max |
| `BNMN` | debo 100 → N debe 60 → M debo 50 → N debe 50 | 110 | 150 | **-40** | 110 | -40 (tú debes) | n3 40⅟ | nivel-max |
| `BNMP` | debo 100 → N debe 60 → M debo 50 → P doy 150 | 60 | 0 | **+60** | 0 | +60 (te deben) | n2 60 | nivel-max |
| `BNMQ` | debo 100 → N debe 60 → M debo 50 → Q doy 90 | 60 | 60 | **+0** | 60 | +0 (al día) | — | nivel-max |
| `BNMR` | debo 100 → N debe 60 → M debo 50 → R doy 225 | 60 | 0 | **+135** | 0 | +135 (te deben) | n2 60 · a favor tuyo 75 | nivel-max |
| `BNMS` | debo 100 → N debe 60 → M debo 50 → S debe 135 | 195 | 150 | **+45** | 150 | +45 (te deben) | n4 45⅟ | nivel-max |
| `BNPE` | debo 100 → N debe 60 → P doy 100 → E recibido 60 | 0 | 0 | **+0** | 0 | +0 (al día) | — | nivel-max |
| `BNPF` | debo 100 → N debe 60 → P doy 100 → F recibido 35 | 25 | 0 | **+25** | 0 | +25 (te deben) | n2 25⅟ | nivel-max |
| `BNPG` | debo 100 → N debe 60 → P doy 100 → G recibido 90 | 0 | 0 | **-30** | 0 | -30 (tú debes) |  · a favor deudor 30 | nivel-max |
| `BNPI` | debo 100 → N debe 60 → P doy 100 → I debo 60 | 60 | 60 | **+0** | 60 | +0 (al día) | — | nivel-max |
| `BNPM` | debo 100 → N debe 60 → P doy 100 → M debe 75 | 135 | 0 | **+135** | 0 | +135 (te deben) | n2 60, n4 75 | nivel-max |
| `BNPN` | debo 100 → N debe 60 → P doy 100 → N debo 35 | 60 | 35 | **+25** | 35 | +25 (te deben) | n2 25⅟ | nivel-max |
| `BNPR` | debo 100 → N debe 60 → P doy 100 → R doy 50 | 60 | 0 | **+110** | 0 | +110 (te deben) | n2 60 · a favor tuyo 50 | nivel-max |
| `BNPS` | debo 100 → N debe 60 → P doy 100 → S debo 90 | 60 | 90 | **-30** | 60 | -30 (tú debes) | n4 30⅟ | nivel-max |
| `BNQE` | debo 100 → N debe 60 → Q doy 60 → E recibido 60 | 0 | 40 | **-40** | 0 | -40 (tú debes) | n1 40⅟ | nivel-max |
| `BNQF` | debo 100 → N debe 60 → Q doy 60 → F recibido 35 | 25 | 40 | **-15** | 25 | -15 (tú debes) | n1 15⅟ | nivel-max |
| `BNQG` | debo 100 → N debe 60 → Q doy 60 → G recibido 90 | 0 | 40 | **-70** | 0 | -70 (tú debes) | n1 40⅟ · a favor deudor 30 | nivel-max |
| `BNQI` | debo 100 → N debe 60 → Q doy 60 → I debo 20 | 60 | 60 | **+0** | 60 | +0 (al día) | — | nivel-max |
| `BNQM` | debo 100 → N debe 60 → Q doy 60 → M debe 25 | 85 | 40 | **+45** | 40 | +45 (te deben) | n2 20⅟, n4 25 | nivel-max |
| `BNQN` | debo 100 → N debe 60 → Q doy 60 → N debo 10 | 60 | 50 | **+10** | 50 | +10 (te deben) | n2 10⅟ | nivel-max |
| `BNQP` | debo 100 → N debe 60 → Q doy 60 → P doy 40 | 60 | 0 | **+60** | 0 | +60 (te deben) | n2 60 | nivel-max |
| `BNQQ` | debo 100 → N debe 60 → Q doy 60 → Q doy 20 | 60 | 20 | **+40** | 20 | +40 (te deben) | n2 40⅟ | nivel-max |
| `BNQR` | debo 100 → N debe 60 → Q doy 60 → R doy 60 | 60 | 0 | **+80** | 0 | +80 (te deben) | n2 60 · a favor tuyo 20 | nivel-max |
| `BNQS` | debo 100 → N debe 60 → Q doy 60 → S debo 30 | 60 | 70 | **-10** | 60 | -10 (tú debes) | n4 10⅟ | nivel-max |
| `BNRE` | debo 100 → N debe 60 → R doy 150 → E recibido 60 | 0 | 0 | **+50** | 0 | +50 (te deben) |  · a favor tuyo 50 | nivel-max |
| `BNRF` | debo 100 → N debe 60 → R doy 150 → F recibido 35 | 25 | 0 | **+75** | 0 | +75 (te deben) | n2 25⅟ · a favor tuyo 50 | nivel-max |
| `BNRG` | debo 100 → N debe 60 → R doy 150 → G recibido 90 | 0 | 0 | **+20** | 0 | +20 (te deben) |  · a favor deudor 30 · a favor tuyo 50 | nivel-max |
| `BNRI` | debo 100 → N debe 60 → R doy 150 → I debo 110 | 60 | 60 | **+0** | 60 | +0 (al día) | — | nivel-max |
| `BNRM` | debo 100 → N debe 60 → R doy 150 → M debe 140 | 200 | 0 | **+250** | 0 | +250 (te deben) | n2 60, n4 140 · a favor tuyo 50 | nivel-max |
| `BNRN` | debo 100 → N debe 60 → R doy 150 → N debo 65 | 60 | 15 | **+45** | 15 | +45 (te deben) | n2 45⅟ | nivel-max |
| `BNRR` | debo 100 → N debe 60 → R doy 150 → R doy 50 | 60 | 0 | **+160** | 0 | +160 (te deben) | n2 60 · a favor tuyo 100 | nivel-max |
| `BNRS` | debo 100 → N debe 60 → R doy 150 → S debo 165 | 60 | 115 | **-55** | 60 | -55 (tú debes) | n4 55⅟ | nivel-max |
| `BNSE` | debo 100 → N debe 60 → S debe 60 → E recibido 120 | 0 | 100 | **-100** | 0 | -100 (tú debes) | n1 100 | nivel-max |
| `BNSF` | debo 100 → N debe 60 → S debe 60 → F recibido 70 | 50 | 100 | **-50** | 50 | -50 (tú debes) | n1 50⅟ | nivel-max |
| `BNSG` | debo 100 → N debe 60 → S debe 60 → G recibido 180 | 0 | 100 | **-160** | 0 | -160 (tú debes) | n1 100 · a favor deudor 60 | nivel-max |
| `BNSI` | debo 100 → N debe 60 → S debe 60 → I debo 20 | 120 | 120 | **+0** | 120 | +0 (al día) | — | nivel-max |
| `BNSM` | debo 100 → N debe 60 → S debe 60 → M debe 25 | 145 | 100 | **+45** | 100 | +45 (te deben) | n3 20⅟, n4 25 | nivel-max |
| `BNSN` | debo 100 → N debe 60 → S debe 60 → N debo 10 | 120 | 110 | **+10** | 110 | +10 (te deben) | n3 10⅟ | nivel-max |
| `BNSP` | debo 100 → N debe 60 → S debe 60 → P doy 100 | 120 | 0 | **+120** | 0 | +120 (te deben) | n2 60, n3 60 | nivel-max |
| `BNSQ` | debo 100 → N debe 60 → S debe 60 → Q doy 60 | 120 | 40 | **+80** | 40 | +80 (te deben) | n2 20⅟, n3 60 | nivel-max |
| `BNSR` | debo 100 → N debe 60 → S debe 60 → R doy 150 | 120 | 0 | **+170** | 0 | +170 (te deben) | n2 60, n3 60 · a favor tuyo 50 | nivel-max |
| `BNSS` | debo 100 → N debe 60 → S debe 60 → S debo 30 | 120 | 130 | **-10** | 120 | -10 (tú debes) | n4 10⅟ | nivel-max |
| `BPGG` | debo 100 → P doy 100 → G recibido 50 → G recibido 50 | 0 | 0 | **-100** | 0 | -100 (tú debes) |  · a favor deudor 100 | nivel-max |
| `BPGI` | debo 100 → P doy 100 → G recibido 50 → I debe 50 | 0 | 0 | **+0** | 0 | +0 (al día) | — | nivel-max |
| `BPGM` | debo 100 → P doy 100 → G recibido 50 → M debo 60 | 0 | 60 | **-110** | 0 | -110 (tú debes) | n4 60 · a favor deudor 50 | nivel-max |
| `BPGN` | debo 100 → P doy 100 → G recibido 50 → N debe 30 | 0 | 0 | **-20** | 0 | -20 (tú debes) |  · a favor deudor 20 | nivel-max |
| `BPGR` | debo 100 → P doy 100 → G recibido 50 → R doy 50 | 0 | 0 | **+0** | 0 | +0 (al día) |  · a favor deudor 50 · a favor tuyo 50 | nivel-max |
| `BPGS` | debo 100 → P doy 100 → G recibido 50 → S debe 75 | 25 | 0 | **+25** | 0 | +25 (te deben) | n4 25⅟ | nivel-max |
| `BPRG` | debo 100 → P doy 100 → R doy 50 → G recibido 50 | 0 | 0 | **+0** | 0 | +0 (al día) |  · a favor deudor 50 · a favor tuyo 50 | nivel-max |
| `BPRI` | debo 100 → P doy 100 → R doy 50 → I debo 50 | 0 | 0 | **+0** | 0 | +0 (al día) | — | nivel-max |
| `BPRM` | debo 100 → P doy 100 → R doy 50 → M debe 60 | 60 | 0 | **+110** | 0 | +110 (te deben) | n4 60 · a favor tuyo 50 | nivel-max |
| `BPRN` | debo 100 → P doy 100 → R doy 50 → N debo 30 | 0 | 0 | **+20** | 0 | +20 (te deben) |  · a favor tuyo 20 | nivel-max |
| `BPRR` | debo 100 → P doy 100 → R doy 50 → R doy 50 | 0 | 0 | **+100** | 0 | +100 (te deben) |  · a favor tuyo 100 | nivel-max |
| `BPRS` | debo 100 → P doy 100 → R doy 50 → S debo 75 | 0 | 25 | **-25** | 0 | -25 (tú debes) | n4 25⅟ | nivel-max |
| `BPXE` | debo 100 → P doy 100 → X debe 50 → E recibido 50 | 0 | 0 | **+0** | 0 | +0 (al día) | — | nivel-max |
| `BPXF` | debo 100 → P doy 100 → X debe 50 → F recibido 30 | 20 | 0 | **+20** | 0 | +20 (te deben) | n3 20⅟ | nivel-max |
| `BPXG` | debo 100 → P doy 100 → X debe 50 → G recibido 75 | 0 | 0 | **-25** | 0 | -25 (tú debes) |  · a favor deudor 25 | nivel-max |
| `BPXI` | debo 100 → P doy 100 → X debe 50 → I debo 50 | 50 | 50 | **+0** | 50 | +0 (al día) | — | nivel-max |
| `BPXM` | debo 100 → P doy 100 → X debe 50 → M debe 60 | 110 | 0 | **+110** | 0 | +110 (te deben) | n3 50, n4 60 | nivel-max |
| `BPXN` | debo 100 → P doy 100 → X debe 50 → N debo 30 | 50 | 30 | **+20** | 30 | +20 (te deben) | n3 20⅟ | nivel-max |
| `BPXR` | debo 100 → P doy 100 → X debe 50 → R doy 50 | 50 | 0 | **+100** | 0 | +100 (te deben) | n3 50 · a favor tuyo 50 | nivel-max |
| `BPXS` | debo 100 → P doy 100 → X debe 50 → S debo 75 | 50 | 75 | **-25** | 50 | -25 (tú debes) | n4 25⅟ | nivel-max |
| `BPYG` | debo 100 → P doy 100 → Y debo 50 → G recibido 50 | 0 | 50 | **-100** | 0 | -100 (tú debes) | n3 50 · a favor deudor 50 | nivel-max |
| `BPYI` | debo 100 → P doy 100 → Y debo 50 → I debe 50 | 50 | 50 | **+0** | 50 | +0 (al día) | — | nivel-max |
| `BPYM` | debo 100 → P doy 100 → Y debo 50 → M debo 60 | 0 | 110 | **-110** | 0 | -110 (tú debes) | n3 50, n4 60 | nivel-max |
| `BPYN` | debo 100 → P doy 100 → Y debo 50 → N debe 30 | 30 | 50 | **-20** | 30 | -20 (tú debes) | n3 20⅟ | nivel-max |
| `BPYP` | debo 100 → P doy 100 → Y debo 50 → P doy 50 | 0 | 0 | **+0** | 0 | +0 (al día) | — | nivel-max |
| `BPYQ` | debo 100 → P doy 100 → Y debo 50 → Q doy 30 | 0 | 20 | **-20** | 0 | -20 (tú debes) | n3 20⅟ | nivel-max |
| `BPYR` | debo 100 → P doy 100 → Y debo 50 → R doy 75 | 0 | 0 | **+25** | 0 | +25 (te deben) |  · a favor tuyo 25 | nivel-max |
| `BPYS` | debo 100 → P doy 100 → Y debo 50 → S debe 75 | 75 | 50 | **+25** | 50 | +25 (te deben) | n4 25⅟ | nivel-max |
| `BQGG` | debo 100 → Q doy 60 → G recibido 50 → G recibido 50 | 0 | 40 | **-140** | 0 | -140 (tú debes) | n1 40⅟ · a favor deudor 100 | nivel-max |
| `BQGI` | debo 100 → Q doy 60 → G recibido 50 → I debe 90 | 40 | 40 | **+0** | 40 | +0 (al día) | — | nivel-max |
| `BQGM` | debo 100 → Q doy 60 → G recibido 50 → M debo 110 | 0 | 150 | **-200** | 0 | -200 (tú debes) | n1 40⅟, n4 110 · a favor deudor 50 | nivel-max |
| `BQGN` | debo 100 → Q doy 60 → G recibido 50 → N debe 50 | 0 | 40 | **-40** | 0 | -40 (tú debes) | n1 40⅟ | nivel-max |
| `BQGP` | debo 100 → Q doy 60 → G recibido 50 → P doy 40 | 0 | 0 | **-50** | 0 | -50 (tú debes) |  · a favor deudor 50 | nivel-max |
| `BQGQ` | debo 100 → Q doy 60 → G recibido 50 → Q doy 20 | 0 | 20 | **-70** | 0 | -70 (tú debes) | n1 20⅟ · a favor deudor 50 | nivel-max |
| `BQGR` | debo 100 → Q doy 60 → G recibido 50 → R doy 60 | 0 | 0 | **-30** | 0 | -30 (tú debes) |  · a favor deudor 50 · a favor tuyo 20 | nivel-max |
| `BQGS` | debo 100 → Q doy 60 → G recibido 50 → S debe 135 | 85 | 40 | **+45** | 40 | +45 (te deben) | n4 45⅟ | nivel-max |
| `BQIE` | debo 100 → Q doy 60 → I debe 40 → E recibido 40 | 0 | 40 | **-40** | 0 | -40 (tú debes) | n1 40⅟ | nivel-max |
| `BQIF` | debo 100 → Q doy 60 → I debe 40 → F recibido 20 | 20 | 40 | **-20** | 20 | -20 (tú debes) | n1 20⅟ | nivel-max |
| `BQIG` | debo 100 → Q doy 60 → I debe 40 → G recibido 60 | 0 | 40 | **-60** | 0 | -60 (tú debes) | n1 40⅟ · a favor deudor 20 | nivel-max |
| `BQIP` | debo 100 → Q doy 60 → I debe 40 → P doy 40 | 40 | 0 | **+40** | 0 | +40 (te deben) | n3 40 | nivel-max |
| `BQIQ` | debo 100 → Q doy 60 → I debe 40 → Q doy 20 | 40 | 20 | **+20** | 20 | +20 (te deben) | n3 20⅟ | nivel-max |
| `BQIR` | debo 100 → Q doy 60 → I debe 40 → R doy 60 | 40 | 0 | **+60** | 0 | +60 (te deben) | n3 40 · a favor tuyo 20 | nivel-max |
| `BQIX` | debo 100 → Q doy 60 → I debe 40 → X debe 50 | 90 | 40 | **+50** | 40 | +50 (te deben) | n4 50 | nivel-max |
| `BQIY` | debo 100 → Q doy 60 → I debe 40 → Y debo 50 | 40 | 90 | **-50** | 40 | -50 (tú debes) | n4 50 | nivel-max |
| `BQMG` | debo 100 → Q doy 60 → M debo 50 → G recibido 50 | 0 | 90 | **-140** | 0 | -140 (tú debes) | n1 40⅟, n3 50 · a favor deudor 50 | nivel-max |
| `BQMI` | debo 100 → Q doy 60 → M debo 50 → I debe 90 | 90 | 90 | **+0** | 90 | +0 (al día) | — | nivel-max |
| `BQMM` | debo 100 → Q doy 60 → M debo 50 → M debo 110 | 0 | 200 | **-200** | 0 | -200 (tú debes) | n1 40⅟, n3 50, n4 110 | nivel-max |
| `BQMN` | debo 100 → Q doy 60 → M debo 50 → N debe 50 | 50 | 90 | **-40** | 50 | -40 (tú debes) | n3 40⅟ | nivel-max |
| `BQMP` | debo 100 → Q doy 60 → M debo 50 → P doy 90 | 0 | 0 | **+0** | 0 | +0 (al día) | — | nivel-max |
| `BQMQ` | debo 100 → Q doy 60 → M debo 50 → Q doy 50 | 0 | 40 | **-40** | 0 | -40 (tú debes) | n3 40⅟ | nivel-max |
| `BQMR` | debo 100 → Q doy 60 → M debo 50 → R doy 135 | 0 | 0 | **+45** | 0 | +45 (te deben) |  · a favor tuyo 45 | nivel-max |
| `BQMS` | debo 100 → Q doy 60 → M debo 50 → S debe 135 | 135 | 90 | **+45** | 90 | +45 (te deben) | n4 45⅟ | nivel-max |
| `BQNE` | debo 100 → Q doy 60 → N debe 20 → E recibido 20 | 0 | 40 | **-40** | 0 | -40 (tú debes) | n1 40⅟ | nivel-max |
| `BQNF` | debo 100 → Q doy 60 → N debe 20 → F recibido 10 | 10 | 40 | **-30** | 10 | -30 (tú debes) | n1 30⅟ | nivel-max |
| `BQNG` | debo 100 → Q doy 60 → N debe 20 → G recibido 30 | 0 | 40 | **-50** | 0 | -50 (tú debes) | n1 40⅟ · a favor deudor 10 | nivel-max |
| `BQNI` | debo 100 → Q doy 60 → N debe 20 → I debe 20 | 40 | 40 | **+0** | 40 | +0 (al día) | — | nivel-max |
| `BQNM` | debo 100 → Q doy 60 → N debe 20 → M debo 25 | 20 | 65 | **-45** | 20 | -45 (tú debes) | n1 20⅟, n4 25 | nivel-max |
| `BQNN` | debo 100 → Q doy 60 → N debe 20 → N debe 10 | 30 | 40 | **-10** | 30 | -10 (tú debes) | n1 10⅟ | nivel-max |
| `BQNP` | debo 100 → Q doy 60 → N debe 20 → P doy 40 | 20 | 0 | **+20** | 0 | +20 (te deben) | n3 20 | nivel-max |
| `BQNQ` | debo 100 → Q doy 60 → N debe 20 → Q doy 20 | 20 | 20 | **+0** | 20 | +0 (al día) | — | nivel-max |
| `BQNR` | debo 100 → Q doy 60 → N debe 20 → R doy 60 | 20 | 0 | **+40** | 0 | +40 (te deben) | n3 20 · a favor tuyo 20 | nivel-max |
| `BQNS` | debo 100 → Q doy 60 → N debe 20 → S debe 30 | 50 | 40 | **+10** | 40 | +10 (te deben) | n4 10⅟ | nivel-max |
| `BQPG` | debo 100 → Q doy 60 → P doy 40 → G recibido 50 | 0 | 0 | **-50** | 0 | -50 (tú debes) |  · a favor deudor 50 | nivel-max |
| `BQPR` | debo 100 → Q doy 60 → P doy 40 → R doy 50 | 0 | 0 | **+50** | 0 | +50 (te deben) |  · a favor tuyo 50 | nivel-max |
| `BQPX` | debo 100 → Q doy 60 → P doy 40 → X debe 50 | 50 | 0 | **+50** | 0 | +50 (te deben) | n4 50 | nivel-max |
| `BQPY` | debo 100 → Q doy 60 → P doy 40 → Y debo 50 | 0 | 50 | **-50** | 0 | -50 (tú debes) | n4 50 | nivel-max |
| `BQRG` | debo 100 → Q doy 60 → R doy 60 → G recibido 50 | 0 | 0 | **-30** | 0 | -30 (tú debes) |  · a favor deudor 50 · a favor tuyo 20 | nivel-max |
| `BQRI` | debo 100 → Q doy 60 → R doy 60 → I debo 20 | 0 | 0 | **+0** | 0 | +0 (al día) | — | nivel-max |
| `BQRM` | debo 100 → Q doy 60 → R doy 60 → M debe 25 | 25 | 0 | **+45** | 0 | +45 (te deben) | n4 25 · a favor tuyo 20 | nivel-max |
| `BQRN` | debo 100 → Q doy 60 → R doy 60 → N debo 10 | 0 | 0 | **+10** | 0 | +10 (te deben) |  · a favor tuyo 10 | nivel-max |
| `BQRR` | debo 100 → Q doy 60 → R doy 60 → R doy 50 | 0 | 0 | **+70** | 0 | +70 (te deben) |  · a favor tuyo 70 | nivel-max |
| `BQRS` | debo 100 → Q doy 60 → R doy 60 → S debo 30 | 0 | 10 | **-10** | 0 | -10 (tú debes) | n4 10⅟ | nivel-max |
| `BQSE` | debo 100 → Q doy 60 → S debe 60 → E recibido 60 | 0 | 40 | **-40** | 0 | -40 (tú debes) | n1 40⅟ | nivel-max |
| `BQSF` | debo 100 → Q doy 60 → S debe 60 → F recibido 35 | 25 | 40 | **-15** | 25 | -15 (tú debes) | n1 15⅟ | nivel-max |
| `BQSG` | debo 100 → Q doy 60 → S debe 60 → G recibido 90 | 0 | 40 | **-70** | 0 | -70 (tú debes) | n1 40⅟ · a favor deudor 30 | nivel-max |
| `BQSI` | debo 100 → Q doy 60 → S debe 60 → I debo 20 | 60 | 60 | **+0** | 60 | +0 (al día) | — | nivel-max |
| `BQSM` | debo 100 → Q doy 60 → S debe 60 → M debe 25 | 85 | 40 | **+45** | 40 | +45 (te deben) | n3 20⅟, n4 25 | nivel-max |
| `BQSN` | debo 100 → Q doy 60 → S debe 60 → N debo 10 | 60 | 50 | **+10** | 50 | +10 (te deben) | n3 10⅟ | nivel-max |
| `BQSP` | debo 100 → Q doy 60 → S debe 60 → P doy 40 | 60 | 0 | **+60** | 0 | +60 (te deben) | n3 60 | nivel-max |
| `BQSQ` | debo 100 → Q doy 60 → S debe 60 → Q doy 20 | 60 | 20 | **+40** | 20 | +40 (te deben) | n3 40⅟ | nivel-max |
| `BQSR` | debo 100 → Q doy 60 → S debe 60 → R doy 60 | 60 | 0 | **+80** | 0 | +80 (te deben) | n3 60 · a favor tuyo 20 | nivel-max |
| `BQSS` | debo 100 → Q doy 60 → S debe 60 → S debo 30 | 60 | 70 | **-10** | 60 | -10 (tú debes) | n4 10⅟ | nivel-max |
| `BRGG` | debo 100 → R doy 150 → G recibido 50 → G recibido 50 | 0 | 0 | **-50** | 0 | -50 (tú debes) |  · a favor deudor 100 · a favor tuyo 50 | nivel-max |
| `BRGR` | debo 100 → R doy 150 → G recibido 50 → R doy 50 | 0 | 0 | **+50** | 0 | +50 (te deben) |  · a favor deudor 50 · a favor tuyo 100 | nivel-max |
| `BRGX` | debo 100 → R doy 150 → G recibido 50 → X debe 50 | 0 | 0 | **+50** | 0 | +50 (te deben) |  · a favor tuyo 50 | nivel-max |
| `BRGY` | debo 100 → R doy 150 → G recibido 50 → Y debo 50 | 0 | 0 | **-50** | 0 | -50 (tú debes) |  · a favor deudor 50 | nivel-max |
| `BRIG` | debo 100 → R doy 150 → I debo 50 → G recibido 50 | 0 | 0 | **-50** | 0 | -50 (tú debes) |  · a favor deudor 50 | nivel-max |
| `BRIR` | debo 100 → R doy 150 → I debo 50 → R doy 50 | 0 | 0 | **+50** | 0 | +50 (te deben) |  · a favor tuyo 50 | nivel-max |
| `BRIX` | debo 100 → R doy 150 → I debo 50 → X debe 50 | 50 | 0 | **+50** | 0 | +50 (te deben) | n4 50 | nivel-max |
| `BRIY` | debo 100 → R doy 150 → I debo 50 → Y debo 50 | 0 | 50 | **-50** | 0 | -50 (tú debes) | n4 50 | nivel-max |
| `BRME` | debo 100 → R doy 150 → M debe 60 → E recibido 60 | 0 | 0 | **+50** | 0 | +50 (te deben) |  · a favor tuyo 50 | nivel-max |
| `BRMF` | debo 100 → R doy 150 → M debe 60 → F recibido 35 | 25 | 0 | **+75** | 0 | +75 (te deben) | n3 25⅟ · a favor tuyo 50 | nivel-max |
| `BRMG` | debo 100 → R doy 150 → M debe 60 → G recibido 90 | 0 | 0 | **+20** | 0 | +20 (te deben) |  · a favor deudor 30 · a favor tuyo 50 | nivel-max |
| `BRMI` | debo 100 → R doy 150 → M debe 60 → I debo 110 | 60 | 60 | **+0** | 60 | +0 (al día) | — | nivel-max |
| `BRMM` | debo 100 → R doy 150 → M debe 60 → M debe 140 | 200 | 0 | **+250** | 0 | +250 (te deben) | n3 60, n4 140 · a favor tuyo 50 | nivel-max |
| `BRMN` | debo 100 → R doy 150 → M debe 60 → N debo 65 | 60 | 15 | **+45** | 15 | +45 (te deben) | n3 45⅟ | nivel-max |
| `BRMR` | debo 100 → R doy 150 → M debe 60 → R doy 50 | 60 | 0 | **+160** | 0 | +160 (te deben) | n3 60 · a favor tuyo 100 | nivel-max |
| `BRMS` | debo 100 → R doy 150 → M debe 60 → S debo 165 | 60 | 115 | **-55** | 60 | -55 (tú debes) | n4 55⅟ | nivel-max |
| `BRNG` | debo 100 → R doy 150 → N debo 30 → G recibido 50 | 0 | 0 | **-30** | 0 | -30 (tú debes) |  · a favor deudor 50 · a favor tuyo 20 | nivel-max |
| `BRNI` | debo 100 → R doy 150 → N debo 30 → I debo 20 | 0 | 0 | **+0** | 0 | +0 (al día) | — | nivel-max |
| `BRNM` | debo 100 → R doy 150 → N debo 30 → M debe 25 | 25 | 0 | **+45** | 0 | +45 (te deben) | n4 25 · a favor tuyo 20 | nivel-max |
| `BRNN` | debo 100 → R doy 150 → N debo 30 → N debo 10 | 0 | 0 | **+10** | 0 | +10 (te deben) |  · a favor tuyo 10 | nivel-max |
| `BRNR` | debo 100 → R doy 150 → N debo 30 → R doy 50 | 0 | 0 | **+70** | 0 | +70 (te deben) |  · a favor tuyo 70 | nivel-max |
| `BRNS` | debo 100 → R doy 150 → N debo 30 → S debo 30 | 0 | 10 | **-10** | 0 | -10 (tú debes) | n4 10⅟ | nivel-max |
| `BRSG` | debo 100 → R doy 150 → S debo 75 → G recibido 50 | 0 | 25 | **-75** | 0 | -75 (tú debes) | n3 25⅟ · a favor deudor 50 | nivel-max |
| `BRSI` | debo 100 → R doy 150 → S debo 75 → I debe 25 | 25 | 25 | **+0** | 25 | +0 (al día) | — | nivel-max |
| `BRSM` | debo 100 → R doy 150 → S debo 75 → M debo 30 | 0 | 55 | **-55** | 0 | -55 (tú debes) | n3 25⅟, n4 30 | nivel-max |
| `BRSN` | debo 100 → R doy 150 → S debo 75 → N debe 15 | 15 | 25 | **-10** | 15 | -10 (tú debes) | n3 10⅟ | nivel-max |
| `BRSP` | debo 100 → R doy 150 → S debo 75 → P doy 25 | 0 | 0 | **+0** | 0 | +0 (al día) | — | nivel-max |
| `BRSQ` | debo 100 → R doy 150 → S debo 75 → Q doy 15 | 0 | 10 | **-10** | 0 | -10 (tú debes) | n3 10⅟ | nivel-max |
| `BRSR` | debo 100 → R doy 150 → S debo 75 → R doy 40 | 0 | 0 | **+15** | 0 | +15 (te deben) |  · a favor tuyo 15 | nivel-max |
| `BRSS` | debo 100 → R doy 150 → S debo 75 → S debe 40 | 40 | 25 | **+15** | 25 | +15 (te deben) | n4 15⅟ | nivel-max |
| `BSEG` | debo 100 → S debe 150 → E recibido 150 → G recibido 50 | 0 | 100 | **-150** | 0 | -150 (tú debes) | n1 100 · a favor deudor 50 | nivel-max |
| `BSEI` | debo 100 → S debe 150 → E recibido 150 → I debe 100 | 100 | 100 | **+0** | 100 | +0 (al día) | — | nivel-max |
| `BSEM` | debo 100 → S debe 150 → E recibido 150 → M debo 125 | 0 | 225 | **-225** | 0 | -225 (tú debes) | n1 100, n4 125 | nivel-max |
| `BSEN` | debo 100 → S debe 150 → E recibido 150 → N debe 60 | 60 | 100 | **-40** | 60 | -40 (tú debes) | n1 40⅟ | nivel-max |
| `BSEP` | debo 100 → S debe 150 → E recibido 150 → P doy 100 | 0 | 0 | **+0** | 0 | +0 (al día) | — | nivel-max |
| `BSEQ` | debo 100 → S debe 150 → E recibido 150 → Q doy 60 | 0 | 40 | **-40** | 0 | -40 (tú debes) | n1 40⅟ | nivel-max |
| `BSER` | debo 100 → S debe 150 → E recibido 150 → R doy 150 | 0 | 0 | **+50** | 0 | +50 (te deben) |  · a favor tuyo 50 | nivel-max |
| `BSES` | debo 100 → S debe 150 → E recibido 150 → S debe 150 | 150 | 100 | **+50** | 100 | +50 (te deben) | n4 50⅟ | nivel-max |
| `BSFE` | debo 100 → S debe 150 → F recibido 90 → E recibido 60 | 0 | 100 | **-100** | 0 | -100 (tú debes) | n1 100 | nivel-max |
| `BSFF` | debo 100 → S debe 150 → F recibido 90 → F recibido 35 | 25 | 100 | **-75** | 25 | -75 (tú debes) | n1 75⅟ | nivel-max |
| `BSFG` | debo 100 → S debe 150 → F recibido 90 → G recibido 90 | 0 | 100 | **-130** | 0 | -130 (tú debes) | n1 100 · a favor deudor 30 | nivel-max |
| `BSFI` | debo 100 → S debe 150 → F recibido 90 → I debe 40 | 100 | 100 | **+0** | 100 | +0 (al día) | — | nivel-max |
| `BSFM` | debo 100 → S debe 150 → F recibido 90 → M debo 50 | 60 | 150 | **-90** | 60 | -90 (tú debes) | n1 40⅟, n4 50 | nivel-max |
| `BSFN` | debo 100 → S debe 150 → F recibido 90 → N debe 20 | 80 | 100 | **-20** | 80 | -20 (tú debes) | n1 20⅟ | nivel-max |
| `BSFP` | debo 100 → S debe 150 → F recibido 90 → P doy 100 | 60 | 0 | **+60** | 0 | +60 (te deben) | n2 60⅟ | nivel-max |
| `BSFQ` | debo 100 → S debe 150 → F recibido 90 → Q doy 60 | 60 | 40 | **+20** | 40 | +20 (te deben) | n2 20⅟ | nivel-max |
| `BSFR` | debo 100 → S debe 150 → F recibido 90 → R doy 150 | 60 | 0 | **+110** | 0 | +110 (te deben) | n2 60⅟ · a favor tuyo 50 | nivel-max |
| `BSFS` | debo 100 → S debe 150 → F recibido 90 → S debe 60 | 120 | 100 | **+20** | 100 | +20 (te deben) | n4 20⅟ | nivel-max |
| `BSGG` | debo 100 → S debe 150 → G recibido 225 → G recibido 50 | 0 | 100 | **-225** | 0 | -225 (tú debes) | n1 100 · a favor deudor 125 | nivel-max |
| `BSGI` | debo 100 → S debe 150 → G recibido 225 → I debe 175 | 100 | 100 | **+0** | 100 | +0 (al día) | — | nivel-max |
| `BSGM` | debo 100 → S debe 150 → G recibido 225 → M debo 220 | 0 | 320 | **-395** | 0 | -395 (tú debes) | n1 100, n4 220 · a favor deudor 75 | nivel-max |
| `BSGN` | debo 100 → S debe 150 → G recibido 225 → N debe 105 | 30 | 100 | **-70** | 30 | -70 (tú debes) | n1 70⅟ | nivel-max |
| `BSGP` | debo 100 → S debe 150 → G recibido 225 → P doy 100 | 0 | 0 | **-75** | 0 | -75 (tú debes) |  · a favor deudor 75 | nivel-max |
| `BSGQ` | debo 100 → S debe 150 → G recibido 225 → Q doy 60 | 0 | 40 | **-115** | 0 | -115 (tú debes) | n1 40⅟ · a favor deudor 75 | nivel-max |
| `BSGR` | debo 100 → S debe 150 → G recibido 225 → R doy 150 | 0 | 0 | **-25** | 0 | -25 (tú debes) |  · a favor deudor 75 · a favor tuyo 50 | nivel-max |
| `BSGS` | debo 100 → S debe 150 → G recibido 225 → S debe 265 | 190 | 100 | **+90** | 100 | +90 (te deben) | n4 90⅟ | nivel-max |
| `BSIE` | debo 100 → S debe 150 → I debo 50 → E recibido 150 | 0 | 150 | **-150** | 0 | -150 (tú debes) | n1 100, n3 50 | nivel-max |
| `BSIF` | debo 100 → S debe 150 → I debo 50 → F recibido 90 | 60 | 150 | **-90** | 60 | -90 (tú debes) | n1 40⅟, n3 50 | nivel-max |
| `BSIG` | debo 100 → S debe 150 → I debo 50 → G recibido 225 | 0 | 150 | **-225** | 0 | -225 (tú debes) | n1 100, n3 50 · a favor deudor 75 | nivel-max |
| `BSIP` | debo 100 → S debe 150 → I debo 50 → P doy 150 | 150 | 0 | **+150** | 0 | +150 (te deben) | n2 150 | nivel-max |
| `BSIQ` | debo 100 → S debe 150 → I debo 50 → Q doy 90 | 150 | 60 | **+90** | 60 | +90 (te deben) | n2 90⅟ | nivel-max |
| `BSIR` | debo 100 → S debe 150 → I debo 50 → R doy 225 | 150 | 0 | **+225** | 0 | +225 (te deben) | n2 150 · a favor tuyo 75 | nivel-max |
| `BSIX` | debo 100 → S debe 150 → I debo 50 → X debe 75 | 225 | 150 | **+75** | 150 | +75 (te deben) | n4 75 | nivel-max |
| `BSIY` | debo 100 → S debe 150 → I debo 50 → Y debo 75 | 150 | 225 | **-75** | 150 | -75 (tú debes) | n4 75 | nivel-max |
| `BSME` | debo 100 → S debe 150 → M debe 60 → E recibido 210 | 0 | 100 | **-100** | 0 | -100 (tú debes) | n1 100 | nivel-max |
| `BSMF` | debo 100 → S debe 150 → M debe 60 → F recibido 125 | 85 | 100 | **-15** | 85 | -15 (tú debes) | n1 15⅟ | nivel-max |
| `BSMG` | debo 100 → S debe 150 → M debe 60 → G recibido 315 | 0 | 100 | **-205** | 0 | -205 (tú debes) | n1 100 · a favor deudor 105 | nivel-max |
| `BSMI` | debo 100 → S debe 150 → M debe 60 → I debo 110 | 210 | 210 | **+0** | 210 | +0 (al día) | — | nivel-max |
| `BSMM` | debo 100 → S debe 150 → M debe 60 → M debe 140 | 350 | 100 | **+250** | 100 | +250 (te deben) | n2 50⅟, n3 60, n4 140 | nivel-max |
| `BSMN` | debo 100 → S debe 150 → M debe 60 → N debo 65 | 210 | 165 | **+45** | 165 | +45 (te deben) | n3 45⅟ | nivel-max |
| `BSMP` | debo 100 → S debe 150 → M debe 60 → P doy 100 | 210 | 0 | **+210** | 0 | +210 (te deben) | n2 150, n3 60 | nivel-max |
| `BSMQ` | debo 100 → S debe 150 → M debe 60 → Q doy 60 | 210 | 40 | **+170** | 40 | +170 (te deben) | n2 110⅟, n3 60 | nivel-max |
| `BSMR` | debo 100 → S debe 150 → M debe 60 → R doy 150 | 210 | 0 | **+260** | 0 | +260 (te deben) | n2 150, n3 60 · a favor tuyo 50 | nivel-max |
| `BSMS` | debo 100 → S debe 150 → M debe 60 → S debo 165 | 210 | 265 | **-55** | 210 | -55 (tú debes) | n4 55⅟ | nivel-max |
| `BSNE` | debo 100 → S debe 150 → N debo 30 → E recibido 150 | 0 | 130 | **-130** | 0 | -130 (tú debes) | n1 100, n3 30 | nivel-max |
| `BSNF` | debo 100 → S debe 150 → N debo 30 → F recibido 90 | 60 | 130 | **-70** | 60 | -70 (tú debes) | n1 40⅟, n3 30 | nivel-max |
| `BSNG` | debo 100 → S debe 150 → N debo 30 → G recibido 225 | 0 | 130 | **-205** | 0 | -205 (tú debes) | n1 100, n3 30 · a favor deudor 75 | nivel-max |
| `BSNI` | debo 100 → S debe 150 → N debo 30 → I debo 20 | 150 | 150 | **+0** | 150 | +0 (al día) | — | nivel-max |
| `BSNM` | debo 100 → S debe 150 → N debo 30 → M debe 25 | 175 | 130 | **+45** | 130 | +45 (te deben) | n2 20⅟, n4 25 | nivel-max |
| `BSNN` | debo 100 → S debe 150 → N debo 30 → N debo 10 | 150 | 140 | **+10** | 140 | +10 (te deben) | n2 10⅟ | nivel-max |
| `BSNP` | debo 100 → S debe 150 → N debo 30 → P doy 130 | 150 | 0 | **+150** | 0 | +150 (te deben) | n2 150 | nivel-max |
| `BSNQ` | debo 100 → S debe 150 → N debo 30 → Q doy 75 | 150 | 55 | **+95** | 55 | +95 (te deben) | n2 95⅟ | nivel-max |
| `BSNR` | debo 100 → S debe 150 → N debo 30 → R doy 195 | 150 | 0 | **+215** | 0 | +215 (te deben) | n2 150 · a favor tuyo 65 | nivel-max |
| `BSNS` | debo 100 → S debe 150 → N debo 30 → S debo 30 | 150 | 160 | **-10** | 150 | -10 (tú debes) | n4 10⅟ | nivel-max |
| `BSPE` | debo 100 → S debe 150 → P doy 100 → E recibido 150 | 0 | 0 | **+0** | 0 | +0 (al día) | — | nivel-max |
| `BSPF` | debo 100 → S debe 150 → P doy 100 → F recibido 90 | 60 | 0 | **+60** | 0 | +60 (te deben) | n2 60⅟ | nivel-max |
| `BSPG` | debo 100 → S debe 150 → P doy 100 → G recibido 225 | 0 | 0 | **-75** | 0 | -75 (tú debes) |  · a favor deudor 75 | nivel-max |
| `BSPI` | debo 100 → S debe 150 → P doy 100 → I debo 150 | 150 | 150 | **+0** | 150 | +0 (al día) | — | nivel-max |
| `BSPM` | debo 100 → S debe 150 → P doy 100 → M debe 190 | 340 | 0 | **+340** | 0 | +340 (te deben) | n2 150, n4 190 | nivel-max |
| `BSPN` | debo 100 → S debe 150 → P doy 100 → N debo 90 | 150 | 90 | **+60** | 90 | +60 (te deben) | n2 60⅟ | nivel-max |
| `BSPR` | debo 100 → S debe 150 → P doy 100 → R doy 50 | 150 | 0 | **+200** | 0 | +200 (te deben) | n2 150 · a favor tuyo 50 | nivel-max |
| `BSPS` | debo 100 → S debe 150 → P doy 100 → S debo 225 | 150 | 225 | **-75** | 150 | -75 (tú debes) | n4 75⅟ | nivel-max |
| `BSQE` | debo 100 → S debe 150 → Q doy 60 → E recibido 150 | 0 | 40 | **-40** | 0 | -40 (tú debes) | n1 40⅟ | nivel-max |
| `BSQF` | debo 100 → S debe 150 → Q doy 60 → F recibido 90 | 60 | 40 | **+20** | 40 | +20 (te deben) | n2 20⅟ | nivel-max |
| `BSQG` | debo 100 → S debe 150 → Q doy 60 → G recibido 225 | 0 | 40 | **-115** | 0 | -115 (tú debes) | n1 40⅟ · a favor deudor 75 | nivel-max |
| `BSQI` | debo 100 → S debe 150 → Q doy 60 → I debo 110 | 150 | 150 | **+0** | 150 | +0 (al día) | — | nivel-max |
| `BSQM` | debo 100 → S debe 150 → Q doy 60 → M debe 140 | 290 | 40 | **+250** | 40 | +250 (te deben) | n2 110⅟, n4 140 | nivel-max |
| `BSQN` | debo 100 → S debe 150 → Q doy 60 → N debo 65 | 150 | 105 | **+45** | 105 | +45 (te deben) | n2 45⅟ | nivel-max |
| `BSQP` | debo 100 → S debe 150 → Q doy 60 → P doy 40 | 150 | 0 | **+150** | 0 | +150 (te deben) | n2 150 | nivel-max |
| `BSQQ` | debo 100 → S debe 150 → Q doy 60 → Q doy 20 | 150 | 20 | **+130** | 20 | +130 (te deben) | n2 130⅟ | nivel-max |
| `BSQR` | debo 100 → S debe 150 → Q doy 60 → R doy 60 | 150 | 0 | **+170** | 0 | +170 (te deben) | n2 150 · a favor tuyo 20 | nivel-max |
| `BSQS` | debo 100 → S debe 150 → Q doy 60 → S debo 165 | 150 | 205 | **-55** | 150 | -55 (tú debes) | n4 55⅟ | nivel-max |
| `BSRE` | debo 100 → S debe 150 → R doy 150 → E recibido 150 | 0 | 0 | **+50** | 0 | +50 (te deben) |  · a favor tuyo 50 | nivel-max |
| `BSRF` | debo 100 → S debe 150 → R doy 150 → F recibido 90 | 60 | 0 | **+110** | 0 | +110 (te deben) | n2 60⅟ · a favor tuyo 50 | nivel-max |
| `BSRG` | debo 100 → S debe 150 → R doy 150 → G recibido 225 | 0 | 0 | **-25** | 0 | -25 (tú debes) |  · a favor deudor 75 · a favor tuyo 50 | nivel-max |
| `BSRI` | debo 100 → S debe 150 → R doy 150 → I debo 200 | 150 | 150 | **+0** | 150 | +0 (al día) | — | nivel-max |
| `BSRM` | debo 100 → S debe 150 → R doy 150 → M debe 250 | 400 | 0 | **+450** | 0 | +450 (te deben) | n2 150, n4 250 · a favor tuyo 50 | nivel-max |
| `BSRN` | debo 100 → S debe 150 → R doy 150 → N debo 120 | 150 | 70 | **+80** | 70 | +80 (te deben) | n2 80⅟ | nivel-max |
| `BSRR` | debo 100 → S debe 150 → R doy 150 → R doy 50 | 150 | 0 | **+250** | 0 | +250 (te deben) | n2 150 · a favor tuyo 100 | nivel-max |
| `BSRS` | debo 100 → S debe 150 → R doy 150 → S debo 300 | 150 | 250 | **-100** | 150 | -100 (tú debes) | n4 100⅟ | nivel-max |

