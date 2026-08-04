# -*- coding: utf-8 -*-
"""Add remaining carefully written place strings (Latin + ko/th/vi/ru/fil)."""
from __future__ import annotations

import json
from pathlib import Path

p = Path(__file__).with_name("place_extra_seed.json")
EXTRA = json.loads(p.read_text(encoding="utf-8"))

EXTRA["ko"] = {
    "tap_to_copy": "\ud0ed\ud558\uc5ec \ubcf5\uc0ac",
    "listed_by": "\uc218\ub85d \ucd9c\ucc98",
    "no_map_position": "\uc774 \ub9e4\uc7a5\uc758 \uc9c0\ub3c4 \uc704\uce58\uac00 \uc5c6\uc2b5\ub2c8\ub2e4",
    "no_map_position_cap": (
        "\uc8fc\uc18c\ub9cc \uacf5\uac1c\ub418\uc5b4 \uc788\uc2b5\ub2c8\ub2e4. "
        "\u300c\uae38\ucc3e\uae30\u300d\ub85c \uac80\uc0c9\ud558\uc138\uc694."
    ),
    "community_from": "{src} \ucee4\ubba4\ub2c8\ud2f0 \ub370\uc774\ud130(\uc624\ub798\ub418\uc5c8\uc744 \uc218 \uc788\uc74c{date})",
    "community_listings": "\ucee4\ubba4\ub2c8\ud2f0 \ubaa9\ub85d",
    "rechecked_community": "{host}\uc5d0\uc11c \uc7ac\ud655\uc778\ud568(\uc5ec\uc804\ud788 \ucee4\ubba4\ub2c8\ud2f0 \ub370\uc774\ud130)",
    "checked_operator": "{host}\uc640 \ub300\uc870 \ud655\uc778\ud568",
    "checked_operator_generic": "\uc6b4\uc601\uc0ac \uacf5\uc2dd \ud398\uc774\uc9c0\uc640 \ub300\uc870 \ud655\uc778\ud568",
    "price_common": "\uc5ec\uae30 \ub098\uc5f4\ub41c {n}\ub300 \uc911 \uac00\uc7a5 \ud754\ud55c \uc694\uae08.",
    "per_machine": "\ubaa9\ub85d \uae30\uc900 1\ub300\ub2f9.",
    "machine_list_no_counts": "\uae30\uccb4 \ubaa9\ub85d\uc740 \uc788\uc73c\ub098 \ub300\uc218 \uc5c6\uc74c",
    "machine_list_no_counts_cap": (
        "\ucee4\ubba4\ub2c8\ud2f0 \ubaa9\ub85d\uc740 \uae30\uccb4 \uc774\ub984\ub9cc \uc788\uace0 "
        "\ub300\uc218 \uc5c6\uc774 \ud558\ud55c\uc77c \ubfd0\uc785\ub2c8\ub2e4."
    ),
    "cab_counts_unavailable": "\ub300\uc218 \uc815\ubcf4 \uc5c6\uc74c",
    "cab_counts_unavailable_cap": "\uc774 \ub9e4\uc7a5 \ucd9c\ucc98\ub294 \ub300\uc218\ub97c \uacf5\uac1c\ud558\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4.",
    "approx_address": "\uc704\uce58\ub294 \uc8fc\uc18c\uc5d0\uc11c",
    "approx_address_cap": "\ucd9c\ucc98\uc5d0 \uc88c\ud45c\uac00 \uc5c6\uc5b4 \uc778\uc1c4 \uc8fc\uc18c\ub97c \uc9c0\uc624\ucf54\ub529\ud55c \uc704\uce58\uc785\ub2c8\ub2e4.",
    "approx_street": "\uc704\uce58\ub294 \uc8fc\uc18c\uc5d0\uc11c(\ub3c4\ub85c \uc218\uc900)",
    "approx_street_cap": "\uac74\ubb3c\uc774 \uc544\ub2c8\ub77c \ub3c4\ub85c\uc5d0 \ub9de\ucdb0 \uba87 \ubb38\uc9dd \uc5b4\uadf3\ub0a0 \uc218 \uc788\uc2b5\ub2c8\ub2e4.",
    "approx_district": "\ub300\ub7b5\uc801 \uc704\uce58(\uad6c \uc218\uc900)",
    "approx_district_cap": "\uc88c\ud45c \uc5c6\uc774 \uc8fc\uc18c\uc758 \uad6c \uc911\uc2ec\uc785\ub2c8\ub2e4(\ub9e4\uc7a5 \uc790\uccb4 \uc544\ub2d8).",
    "approx_city": "\ub300\ub7b5\uc801 \uc704\uce58(\uc2dc \uc218\uc900)",
    "approx_city_cap": "\uc88c\ud45c\uc640 \uad6c \uc774\ub984\uc774 \uc5c6\uc5b4 \uc2dc \uc911\uc2ec\uc785\ub2c8\ub2e4.",
    "back_to": "{label}(\uc73c)\ub85c \ub3cc\uc544\uac00\uae30",
}

# Domain-aware Latin scripts (rhythm arcade UI; keep source brand names in {src})
LATIN = {
    "id": {
        "tap_to_copy": "Ketuk untuk salin",
        "listed_by": "Dicantumkan oleh",
        "no_map_position": "Toko ini tidak punya posisi peta",
        "no_map_position_cap": "Hanya alamat yang dipublikasikan. Gunakan Petunjuk arah untuk mencari.",
        "community_from": "data komunitas dari {src}, mungkin usang{date}",
        "community_listings": "daftar komunitas",
        "rechecked_community": "dicek ulang di {host}, masih data komunitas",
        "checked_operator": "dicek terhadap {host}",
        "checked_operator_generic": "dicek terhadap daftar resmi operator",
        "price_common": "Harga paling umum di antara {n} mesin yang tercantum di sini.",
        "per_machine": "Per mesin, sesuai daftar.",
        "machine_list_no_counts": "Ada daftar mesin, tanpa jumlah kabinet",
        "machine_list_no_counts_cap": (
            "Daftar komunitas menamai mesin di bawah tanpa bilang berapa unit tiap jenis, "
            "jadi ini batas bawah, bukan hitungan pasti."
        ),
        "cab_counts_unavailable": "Jumlah kabinet tidak tersedia",
        "cab_counts_unavailable_cap": "Sumber toko ini tidak memublikasikan berapa banyak mesin.",
        "approx_address": "Posisi dari alamat",
        "approx_address_cap": "Sumber tanpa koordinat; pin di-geocode dari alamat tercetak.",
        "approx_street": "Posisi dari alamat (level jalan)",
        "approx_street_cap": "Ter-geocode ke jalan, bukan bangunan; bisa meleset satu-dua pintu.",
        "approx_district": "Posisi perkiraan (level distrik)",
        "approx_district_cap": "Tanpa koordinat; pin di pusat distrik pada alamat, bukan toko.",
        "approx_city": "Posisi perkiraan (level kota)",
        "approx_city_cap": "Tanpa koordinat dan tanpa nama distrik; pin di pusat kota.",
        "back_to": "Kembali ke {label}",
    },
    "ms": {
        "tap_to_copy": "Ketik untuk salin",
        "listed_by": "Disenaraikan oleh",
        "no_map_position": "Kedai ini tiada kedudukan peta",
        "no_map_position_cap": "Hanya alamat diterbitkan. Gunakan Arah untuk mencari.",
        "community_from": "data komuniti daripada {src}, mungkin lapuk{date}",
        "community_listings": "senarai komuniti",
        "rechecked_community": "disemak semula di {host}, masih data komuniti",
        "checked_operator": "disemak berbanding {host}",
        "checked_operator_generic": "disemak berbanding senarai rasmi pengendali",
        "price_common": "Harga paling biasa merentasi {n} mesin tersenarai di sini.",
        "per_machine": "Setiap mesin, seperti disenaraikan.",
        "machine_list_no_counts": "Ada senarai mesin, tiada bilangan kabinet",
        "machine_list_no_counts_cap": (
            "Senarai komuniti menamakan mesin di bawah tanpa bilangan unit, "
            "jadi ini had bawah, bukan kiraan penuh."
        ),
        "cab_counts_unavailable": "Bilangan kabinet tidak tersedia",
        "cab_counts_unavailable_cap": "Sumber kedai ini tidak menerbitkan berapa banyak mesin.",
        "approx_address": "Kedudukan daripada alamat",
        "approx_address_cap": "Sumber tiada koordinat; pin digeokod daripada alamat bercetak.",
        "approx_street": "Kedudukan daripada alamat (level jalan)",
        "approx_street_cap": "Digeokod ke jalan, bukan bangunan; mungkin silap satu-dua pintu.",
        "approx_district": "Kedudukan anggaran (level daerah)",
        "approx_district_cap": "Tiada koordinat; pin di pusat daerah pada alamat, bukan kedai.",
        "approx_city": "Kedudukan anggaran (level bandar)",
        "approx_city_cap": "Tiada koordinat dan tiada nama daerah; pin di pusat bandar.",
        "back_to": "Kembali ke {label}",
    },
    "es": {
        "tap_to_copy": "Toca para copiar",
        "listed_by": "Listado por",
        "no_map_position": "Este local no tiene posici\u00f3n en el mapa",
        "no_map_position_cap": "Solo se public\u00f3 la direcci\u00f3n. Usa C\u00f3mo llegar para buscarla.",
        "community_from": "datos de la comunidad de {src}; pueden estar desactualizados{date}",
        "community_listings": "listados de la comunidad",
        "rechecked_community": "vuelto a comprobar en {host}; sigue siendo dato comunitario",
        "checked_operator": "comprobado con {host}",
        "checked_operator_generic": "comprobado con el listado oficial del operador",
        "price_common": "Precio m\u00e1s frecuente entre las {n} m\u00e1quinas listadas aqu\u00ed.",
        "per_machine": "Por m\u00e1quina, seg\u00fan el listado.",
        "machine_list_no_counts": "Hay lista de m\u00e1quinas, sin n\u00famero de cabinas",
        "machine_list_no_counts_cap": (
            "El listado comunitario nombra las m\u00e1quinas de abajo sin decir cu\u00e1ntas hay de cada una; "
            "es un m\u00ednimo, no un inventario."
        ),
        "cab_counts_unavailable": "N\u00famero de cabinas no disponible",
        "cab_counts_unavailable_cap": "Las fuentes de este local no publican cu\u00e1ntas m\u00e1quinas tiene.",
        "approx_address": "Posici\u00f3n a partir de la direcci\u00f3n",
        "approx_address_cap": "La fuente no da coordenadas; el pin se geocodific\u00f3 desde la direcci\u00f3n impresa.",
        "approx_street": "Posici\u00f3n a partir de la direcci\u00f3n (nivel calle)",
        "approx_street_cap": "Geocodificado a la calle, no al edificio; puede fallar una o dos puertas.",
        "approx_district": "Posici\u00f3n aproximada (nivel distrito)",
        "approx_district_cap": "Sin coordenadas; el pin es el centro del distrito de la direcci\u00f3n, no el local.",
        "approx_city": "Posici\u00f3n aproximada (nivel ciudad)",
        "approx_city_cap": "Sin coordenadas ni nombre de distrito; el pin es el centro de la ciudad.",
        "back_to": "Volver a {label}",
    },
    "fr": {
        "tap_to_copy": "Appuyer pour copier",
        "listed_by": "R\u00e9f\u00e9renc\u00e9 par",
        "no_map_position": "Ce salon n'a pas de position sur la carte",
        "no_map_position_cap": "Seule l'adresse est publi\u00e9e. Utilisez Itin\u00e9raire pour la chercher.",
        "community_from": "donn\u00e9es communautaires de {src}, peut-\u00eatre obsol\u00e8tes{date}",
        "community_listings": "listes communautaires",
        "rechecked_community": "rev\u00e9rifi\u00e9 sur {host}, toujours des donn\u00e9es communautaires",
        "checked_operator": "v\u00e9rifi\u00e9 aupr\u00e8s de {host}",
        "checked_operator_generic": "v\u00e9rifi\u00e9 aupr\u00e8s de la page officielle de l'exploitant",
        "price_common": "Prix le plus fr\u00e9quent parmi les {n} machines list\u00e9es ici.",
        "per_machine": "Par machine, selon la liste.",
        "machine_list_no_counts": "Liste de machines, sans nombre de bornes",
        "machine_list_no_counts_cap": (
            "La liste communautaire nomme les machines ci-dessous sans dire combien de chacune ; "
            "c'est un plancher, pas un inventaire."
        ),
        "cab_counts_unavailable": "Nombre de bornes indisponible",
        "cab_counts_unavailable_cap": "Les sources de ce salon ne publient pas le nombre de machines.",
        "approx_address": "Position d'apr\u00e8s l'adresse",
        "approx_address_cap": "La source n'a pas de coordonn\u00e9es ; le pin a \u00e9t\u00e9 g\u00e9ocod\u00e9 depuis l'adresse imprim\u00e9e.",
        "approx_street": "Position d'apr\u00e8s l'adresse (niveau rue)",
        "approx_street_cap": "G\u00e9ocod\u00e9 \u00e0 la rue, pas au b\u00e2timent ; peut se tromper d'une ou deux portes.",
        "approx_district": "Position approximative (niveau district)",
        "approx_district_cap": "Sans coordonn\u00e9es ; le pin est le centre du district nomm\u00e9, pas le salon.",
        "approx_city": "Position approximative (niveau ville)",
        "approx_city_cap": "Sans coordonn\u00e9es ni nom de district ; le pin est le centre de la ville.",
        "back_to": "Retour \u00e0 {label}",
    },
    "de": {
        "tap_to_copy": "Tippen zum Kopieren",
        "listed_by": "Gelistet von",
        "no_map_position": "Dieser Laden hat keine Kartenposition",
        "no_map_position_cap": "Nur die Adresse ist ver\u00f6ffentlicht. Nutze Route zum Suchen.",
        "community_from": "Community-Daten von {src}, m\u00f6glicherweise veraltet{date}",
        "community_listings": "Community-Listen",
        "rechecked_community": "auf {host} erneut gepr\u00fcft, weiterhin Community-Daten",
        "checked_operator": "gepr\u00fcft gegen {host}",
        "checked_operator_generic": "gepr\u00fcft gegen die offizielle Betreiberseite",
        "price_common": "H\u00e4ufigster Preis unter den {n} hier gelisteten Automaten.",
        "per_machine": "Pro Automat, wie gelistet.",
        "machine_list_no_counts": "Automatenliste, aber keine St\u00fcckzahlen",
        "machine_list_no_counts_cap": (
            "Die Community-Liste nennt die Automaten unten, ohne wie viele von jedem; "
            "das ist eine Untergrenze, keine Inventur."
        ),
        "cab_counts_unavailable": "St\u00fcckzahlen nicht verf\u00fcgbar",
        "cab_counts_unavailable_cap": "Die Quellen dieses Ladens ver\u00f6ffentlichen keine Automatenanzahl.",
        "approx_address": "Position aus der Adresse",
        "approx_address_cap": "Quelle ohne Koordinaten; Pin aus der gedruckten Adresse geocodiert.",
        "approx_street": "Position aus der Adresse (Stra\u00dfenebene)",
        "approx_street_cap": "Auf die Stra\u00dfe geocodiert, nicht das Geb\u00e4ude; kann ein, zwei T\u00fcren daneben liegen.",
        "approx_district": "Ungef\u00e4hre Position (Bezirksebene)",
        "approx_district_cap": "Ohne Koordinaten; Pin ist der Bezirksmittelpunkt der Adresse, nicht der Laden.",
        "approx_city": "Ungef\u00e4hre Position (Stadtebene)",
        "approx_city_cap": "Ohne Koordinaten und ohne Bezirksnamen; Pin ist der Stadtmitte.",
        "back_to": "Zur\u00fcck zu {label}",
    },
    "pt": {
        "tap_to_copy": "Toque para copiar",
        "listed_by": "Listado por",
        "no_map_position": "Esta loja n\u00e3o tem posi\u00e7\u00e3o no mapa",
        "no_map_position_cap": "S\u00f3 o endere\u00e7o foi publicado. Use Dire\u00e7\u00f5es para pesquisar.",
        "community_from": "dados da comunidade de {src}; podem estar desatualizados{date}",
        "community_listings": "listagens da comunidade",
        "rechecked_community": "reconferido em {host}; ainda s\u00e3o dados da comunidade",
        "checked_operator": "conferido com {host}",
        "checked_operator_generic": "conferido com a p\u00e1gina oficial do operador",
        "price_common": "Pre\u00e7o mais comum entre as {n} m\u00e1quinas listadas aqui.",
        "per_machine": "Por m\u00e1quina, conforme a lista.",
        "machine_list_no_counts": "H\u00e1 lista de m\u00e1quinas, sem contagem de cabines",
        "machine_list_no_counts_cap": (
            "A lista da comunidade nomeia as m\u00e1quinas abaixo sem dizer quantas de cada; "
            "\u00e9 um piso, n\u00e3o um invent\u00e1rio."
        ),
        "cab_counts_unavailable": "Contagem de cabines indispon\u00edvel",
        "cab_counts_unavailable_cap": "As fontes desta loja n\u00e3o publicam quantas m\u00e1quinas ela tem.",
        "approx_address": "Posi\u00e7\u00e3o a partir do endere\u00e7o",
        "approx_address_cap": "A fonte n\u00e3o tem coordenadas; o pino foi geocodificado do endere\u00e7o impresso.",
        "approx_street": "Posi\u00e7\u00e3o a partir do endere\u00e7o (n\u00edvel rua)",
        "approx_street_cap": "Geocodificado para a rua, n\u00e3o o pr\u00e9dio; pode errar uma ou duas portas.",
        "approx_district": "Posi\u00e7\u00e3o aproximada (n\u00edvel distrito)",
        "approx_district_cap": "Sem coordenadas; o pino \u00e9 o centro do distrito do endere\u00e7o, n\u00e3o a loja.",
        "approx_city": "Posi\u00e7\u00e3o aproximada (n\u00edvel cidade)",
        "approx_city_cap": "Sem coordenadas e sem nome de distrito; o pino \u00e9 o centro da cidade.",
        "back_to": "Voltar para {label}",
    },
    "it": {
        "tap_to_copy": "Tocca per copiare",
        "listed_by": "Elencato da",
        "no_map_position": "Questo locale non ha posizione sulla mappa",
        "no_map_position_cap": "\u00c8 pubblicato solo l'indirizzo. Usa Indicazioni per cercarlo.",
        "community_from": "dati della community da {src}; potrebbero non essere aggiornati{date}",
        "community_listings": "elenchi della community",
        "rechecked_community": "ricontrollato su {host}; restano dati della community",
        "checked_operator": "verificato su {host}",
        "checked_operator_generic": "verificato sulla pagina ufficiale dell'operatore",
        "price_common": "Prezzo pi\u00f9 comune tra le {n} macchine elencate qui.",
        "per_machine": "Per macchina, come da elenco.",
        "machine_list_no_counts": "Elenco macchine senza numero di cabinati",
        "machine_list_no_counts_cap": (
            "L'elenco community nomina le macchine sotto senza dire quante di ciascuna; "
            "\u00e8 un minimo, non un inventario."
        ),
        "cab_counts_unavailable": "Numero di cabinati non disponibile",
        "cab_counts_unavailable_cap": "Le fonti di questo locale non pubblicano quante macchine ha.",
        "approx_address": "Posizione dall'indirizzo",
        "approx_address_cap": "La fonte non ha coordinate; il pin \u00e8 geocodificato dall'indirizzo stampato.",
        "approx_street": "Posizione dall'indirizzo (livello strada)",
        "approx_street_cap": "Geocodificato sulla strada, non sull'edificio; pu\u00f2 sbagliare di una-due porte.",
        "approx_district": "Posizione approssimativa (livello distretto)",
        "approx_district_cap": "Senza coordinate; il pin \u00e8 il centro del distretto nell'indirizzo, non il locale.",
        "approx_city": "Posizione approssimativa (livello citt\u00e0)",
        "approx_city_cap": "Senza coordinate n\u00e9 nome di distretto; il pin \u00e8 il centro della citt\u00e0.",
        "back_to": "Torna a {label}",
    },
    "fil": {
        "tap_to_copy": "I-tap para kopyahin",
        "listed_by": "Nakalista mula sa",
        "no_map_position": "Walang posisyon sa mapa ang tindahang ito",
        "no_map_position_cap": "Address lang ang na-publish. Gamitin ang Direksyon para maghanap.",
        "community_from": "community data mula sa {src}, maaaring luma{date}",
        "community_listings": "mga community listing",
        "rechecked_community": "muling sinuri sa {host}, community data pa rin",
        "checked_operator": "sinuri laban sa {host}",
        "checked_operator_generic": "sinuri laban sa opisyal na listahan ng operator",
        "price_common": "Pinakakaraniwang presyo sa {n} makinang nakalista rito.",
        "per_machine": "Bawat makina, ayon sa listahan.",
        "machine_list_no_counts": "May listahan ng makina, walang bilang ng cabinet",
        "machine_list_no_counts_cap": (
            "Pinangalanan ng community listing ang mga makina sa ibaba nang hindi sinasabi "
            "kung ilan ang bawat isa, kaya ito ay lower bound, hindi buong bilang."
        ),
        "cab_counts_unavailable": "Walang bilang ng cabinet",
        "cab_counts_unavailable_cap": "Hindi nagpa-publish ang mga pinagmulan ng bilang ng makina.",
        "approx_address": "Posisyon mula sa address",
        "approx_address_cap": "Walang coordinates ang source; na-geocode ang pin mula sa naka-print na address.",
        "approx_street": "Posisyon mula sa address (level ng kalsada)",
        "approx_street_cap": "Na-geocode sa kalsada, hindi gusali; maaaring malayo ng isa-dalawang pinto.",
        "approx_district": "Tinatayang posisyon (level ng distrito)",
        "approx_district_cap": "Walang coordinates; ang pin ay gitna ng distrito sa address, hindi ang tindahan.",
        "approx_city": "Tinatayang posisyon (level ng lungsod)",
        "approx_city_cap": "Walang coordinates at walang pangalan ng distrito; gitna ng lungsod ang pin.",
        "back_to": "Bumalik sa {label}",
    },
}

for code, d in LATIN.items():
    EXTRA[code] = d

# Vietnamese with diacritics
EXTRA["vi"] = {
    "tap_to_copy": "Ch\u1ea1m \u0111\u1ec3 sao ch\u00e9p",
    "listed_by": "\u0110\u01b0\u1ee3c li\u1ec7t k\u00ea b\u1edfi",
    "no_map_position": "C\u1eeda h\u00e0ng n\u00e0y kh\u00f4ng c\u00f3 v\u1ecb tr\u00ed tr\u00ean b\u1ea3n \u0111\u1ed3",
    "no_map_position_cap": "Ch\u1ec9 c\u00f4ng b\u1ed1 \u0111\u1ecba ch\u1ec9. D\u00f9ng Ch\u1ec9 \u0111\u01b0\u1eddng \u0111\u1ec3 t\u00ecm.",
    "community_from": "d\u1eef li\u1ec7u c\u1ed9ng \u0111\u1ed3ng t\u1eeb {src}, c\u00f3 th\u1ec3 l\u1ed7i th\u1eddi{date}",
    "community_listings": "danh s\u00e1ch c\u1ed9ng \u0111\u1ed3ng",
    "rechecked_community": "\u0111\u00e3 ki\u1ec3m tra l\u1ea1i tr\u00ean {host}, v\u1eabn l\u00e0 d\u1eef li\u1ec7u c\u1ed9ng \u0111\u1ed3ng",
    "checked_operator": "\u0111\u00e3 \u0111\u1ed1i chi\u1ebfu v\u1edbi {host}",
    "checked_operator_generic": "\u0111\u00e3 \u0111\u1ed1i chi\u1ebfu v\u1edbi trang ch\u00ednh th\u1ee9c c\u1ee7a nh\u00e0 v\u1eadn h\u00e0nh",
    "price_common": "Gi\u00e1 ph\u1ed5 bi\u1ebfn nh\u1ea5t trong {n} m\u00e1y \u0111\u01b0\u1ee3c li\u1ec7t k\u00ea t\u1ea1i \u0111\u00e2y.",
    "per_machine": "M\u1ed7i m\u00e1y, theo danh s\u00e1ch.",
    "machine_list_no_counts": "C\u00f3 danh s\u00e1ch m\u00e1y, kh\u00f4ng c\u00f3 s\u1ed1 l\u01b0\u1ee3ng cabinet",
    "machine_list_no_counts_cap": (
        "Danh s\u00e1ch c\u1ed9ng \u0111\u1ed3ng n\u00eau t\u00ean m\u00e1y b\u00ean d\u01b0\u1edbi m\u00e0 kh\u00f4ng n\u00f3i m\u1ed7i lo\u1ea1i c\u00f3 bao nhi\u00eau, "
        "n\u00ean \u0111\u00e2y l\u00e0 gi\u1edbi h\u1ea1n d\u01b0\u1edbi ch\u1ee9 kh\u00f4ng ph\u1ea3i ki\u1ec3m k\u00ea."
    ),
    "cab_counts_unavailable": "Kh\u00f4ng c\u00f3 s\u1ed1 l\u01b0\u1ee3ng cabinet",
    "cab_counts_unavailable_cap": "Ngu\u1ed3n c\u1ee7a c\u1eeda h\u00e0ng n\u00e0y kh\u00f4ng c\u00f4ng b\u1ed1 s\u1ed1 m\u00e1y.",
    "approx_address": "V\u1ecb tr\u00ed t\u1eeb \u0111\u1ecba ch\u1ec9",
    "approx_address_cap": "Ngu\u1ed3n kh\u00f4ng c\u00f3 t\u1ecda \u0111\u1ed9; ghim \u0111\u01b0\u1ee3c geocode t\u1eeb \u0111\u1ecba ch\u1ec9 in.",
    "approx_street": "V\u1ecb tr\u00ed t\u1eeb \u0111\u1ecba ch\u1ec9 (c\u1ea5p \u0111\u01b0\u1eddng)",
    "approx_street_cap": "Geocode t\u1edbi \u0111\u01b0\u1eddng ch\u1ee9 kh\u00f4ng ph\u1ea3i t\u00f2a nh\u00e0; c\u00f3 th\u1ec3 l\u1ec7ch m\u1ed9t-hai c\u1eeda.",
    "approx_district": "V\u1ecb tr\u00ed x\u1ea5p x\u1ec9 (c\u1ea5p qu\u1eadn)",
    "approx_district_cap": "Kh\u00f4ng t\u1ecda \u0111\u1ed9; ghim \u1edf trung t\u00e2m qu\u1eadn trong \u0111\u1ecba ch\u1ec9, kh\u00f4ng ph\u1ea3i c\u1eeda h\u00e0ng.",
    "approx_city": "V\u1ecb tr\u00ed x\u1ea5p x\u1ec9 (c\u1ea5p th\u00e0nh ph\u1ed1)",
    "approx_city_cap": "Kh\u00f4ng t\u1ecda \u0111\u1ed9 v\u00e0 kh\u00f4ng t\u00ean qu\u1eadn; ghim \u1edf trung t\u00e2m th\u00e0nh ph\u1ed1.",
    "back_to": "Quay l\u1ea1i {label}",
}

# Thai (full)
EXTRA["th"] = {
    "tap_to_copy": "\u0e41\u0e15\u0e30\u0e40\u0e1e\u0e37\u0e48\u0e2d\u0e04\u0e31\u0e14\u0e25\u0e2d\u0e01",
    "listed_by": "\u0e41\u0e2b\u0e25\u0e48\u0e07\u0e17\u0e35\u0e48\u0e25\u0e07\u0e02\u0e49\u0e2d\u0e21\u0e39\u0e25",
    "no_map_position": "\u0e23\u0e49\u0e32\u0e19\u0e19\u0e35\u0e49\u0e44\u0e21\u0e48\u0e21\u0e35\u0e15\u0e33\u0e41\u0e2b\u0e19\u0e48\u0e07\u0e1a\u0e19\u0e41\u0e1c\u0e19\u0e17\u0e35\u0e48",
    "no_map_position_cap": "\u0e40\u0e1c\u0e22\u0e41\u0e1e\u0e23\u0e48\u0e40\u0e09\u0e1e\u0e32\u0e30\u0e17\u0e35\u0e48\u0e2d\u0e22\u0e39\u0e48 \u0e43\u0e0a\u0e49\u300c\u0e40\u0e2a\u0e49\u0e19\u0e17\u0e32\u0e07\u300d\u0e40\u0e1e\u0e37\u0e48\u0e2d\u0e04\u0e49\u0e19\u0e2b\u0e32",
    "community_from": "\u0e02\u0e49\u0e2d\u0e21\u0e39\u0e25\u0e0a\u0e38\u0e21\u0e0a\u0e19\u0e08\u0e32\u0e01 {src} \u0e2d\u0e32\u0e08\u0e25\u0e49\u0e32\u0e2a\u0e21\u0e31\u0e22{date}",
    "community_listings": "\u0e23\u0e32\u0e22\u0e01\u0e32\u0e23\u0e0a\u0e38\u0e21\u0e0a\u0e19",
    "rechecked_community": "\u0e15\u0e23\u0e27\u0e08\u0e0b\u0e49\u0e33\u0e17\u0e35\u0e48 {host} \u0e22\u0e31\u0e07\u0e40\u0e1b\u0e47\u0e19\u0e02\u0e49\u0e2d\u0e21\u0e39\u0e25\u0e0a\u0e38\u0e21\u0e0a\u0e19",
    "checked_operator": "\u0e15\u0e23\u0e27\u0e08\u0e40\u0e17\u0e35\u0e22\u0e1a\u0e01\u0e31\u0e1a {host}",
    "checked_operator_generic": "\u0e15\u0e23\u0e27\u0e08\u0e40\u0e17\u0e35\u0e22\u0e1a\u0e01\u0e31\u0e1a\u0e2b\u0e19\u0e49\u0e32\u0e40\u0e27\u0e47\u0e1a\u0e17\u0e32\u0e07\u0e01\u0e32\u0e23\u0e02\u0e2d\u0e07\u0e1c\u0e39\u0e49\u0e43\u0e2b\u0e49\u0e1a\u0e23\u0e34\u0e01\u0e32\u0e23",
    "price_common": "\u0e23\u0e32\u0e04\u0e32\u0e17\u0e35\u0e48\u0e1e\u0e1a\u0e1a\u0e48\u0e2d\u0e22\u0e17\u0e35\u0e48\u0e2a\u0e38\u0e14\u0e43\u0e19 {n} \u0e15\u0e39\u0e49\u0e17\u0e35\u0e48\u0e23\u0e30\u0e1a\u0e38\u0e44\u0e27\u0e49\u0e17\u0e35\u0e48\u0e19\u0e35\u0e48",
    "per_machine": "\u0e15\u0e48\u0e2d\u0e15\u0e39\u0e49 \u0e15\u0e32\u0e21\u0e23\u0e32\u0e22\u0e01\u0e32\u0e23",
    "machine_list_no_counts": "\u0e21\u0e35\u0e23\u0e32\u0e22\u0e0a\u0e37\u0e48\u0e2d\u0e15\u0e39\u0e49 \u0e41\u0e15\u0e48\u0e44\u0e21\u0e48\u0e21\u0e35\u0e08\u0e33\u0e19\u0e27\u0e19",
    "machine_list_no_counts_cap": (
        "\u0e23\u0e32\u0e22\u0e01\u0e32\u0e23\u0e0a\u0e38\u0e21\u0e0a\u0e19\u0e23\u0e30\u0e1a\u0e38\u0e0a\u0e37\u0e48\u0e2d\u0e15\u0e39\u0e49\u0e14\u0e49\u0e32\u0e19\u0e25\u0e48\u0e32\u0e07"
        "\u0e42\u0e14\u0e22\u0e44\u0e21\u0e48\u0e1a\u0e2d\u0e01\u0e27\u0e48\u0e32\u0e21\u0e35\u0e01\u0e35\u0e48\u0e15\u0e39\u0e49\u0e41\u0e15\u0e48\u0e25\u0e30\u0e0a\u0e19\u0e34\u0e14 "
        "\u0e08\u0e36\u0e07\u0e40\u0e1b\u0e47\u0e19\u0e02\u0e2d\u0e1a\u0e25\u0e48\u0e32\u0e07 \u0e44\u0e21\u0e48\u0e43\u0e0a\u0e48\u0e01\u0e32\u0e23\u0e19\u0e31\u0e1a\u0e08\u0e23\u0e34\u0e07"
    ),
    "cab_counts_unavailable": "\u0e44\u0e21\u0e48\u0e21\u0e35\u0e02\u0e49\u0e2d\u0e21\u0e39\u0e25\u0e08\u0e33\u0e19\u0e27\u0e19\u0e15\u0e39\u0e49",
    "cab_counts_unavailable_cap": "\u0e41\u0e2b\u0e25\u0e48\u0e07\u0e02\u0e2d\u0e07\u0e23\u0e49\u0e32\u0e19\u0e19\u0e35\u0e49\u0e44\u0e21\u0e48\u0e40\u0e1c\u0e22\u0e41\u0e1e\u0e23\u0e48\u0e08\u0e33\u0e19\u0e27\u0e19\u0e15\u0e39\u0e49",
    "approx_address": "\u0e15\u0e33\u0e41\u0e2b\u0e19\u0e48\u0e07\u0e08\u0e32\u0e01\u0e17\u0e35\u0e48\u0e2d\u0e22\u0e39\u0e48",
    "approx_address_cap": "\u0e41\u0e2b\u0e25\u0e48\u0e07\u0e44\u0e21\u0e48\u0e21\u0e35\u0e1e\u0e34\u0e01\u0e31\u0e14 \u0e08\u0e36\u0e07\u0e08\u0e35\u0e42\u0e2d\u0e42\u0e04\u0e49\u0e14\u0e08\u0e32\u0e01\u0e17\u0e35\u0e48\u0e2d\u0e22\u0e39\u0e48\u0e17\u0e35\u0e48\u0e1e\u0e34\u0e21\u0e1e\u0e4c\u0e44\u0e27\u0e49",
    "approx_street": "\u0e15\u0e33\u0e41\u0e2b\u0e19\u0e48\u0e07\u0e08\u0e32\u0e01\u0e17\u0e35\u0e48\u0e2d\u0e22\u0e39\u0e48 (\u0e23\u0e30\u0e14\u0e31\u0e1a\u0e16\u0e19\u0e19)",
    "approx_street_cap": "\u0e08\u0e35\u0e42\u0e2d\u0e42\u0e04\u0e49\u0e14\u0e16\u0e36\u0e07\u0e16\u0e19\u0e19 \u0e44\u0e21\u0e48\u0e43\u0e0a\u0e48\u0e15\u0e31\u0e27\u0e2d\u0e32\u0e04\u0e32\u0e23 \u0e2d\u0e32\u0e08\u0e04\u0e25\u0e32\u0e14\u0e2b\u0e19\u0e36\u0e48\u0e07-\u0e2a\u0e2d\u0e07\u0e1b\u0e23\u0e30\u0e15\u0e39",
    "approx_district": "\u0e15\u0e33\u0e41\u0e2b\u0e19\u0e48\u0e07\u0e42\u0e14\u0e22\u0e1b\u0e23\u0e30\u0e21\u0e32\u0e13 (\u0e23\u0e30\u0e14\u0e31\u0e1a\u0e40\u0e02\u0e15)",
    "approx_district_cap": "\u0e44\u0e21\u0e48\u0e21\u0e35\u0e1e\u0e34\u0e01\u0e31\u0e14 \u0e2b\u0e21\u0e38\u0e14\u0e2d\u0e22\u0e39\u0e48\u0e01\u0e25\u0e32\u0e07\u0e40\u0e02\u0e15\u0e43\u0e19\u0e17\u0e35\u0e48\u0e2d\u0e22\u0e39\u0e48 \u0e44\u0e21\u0e48\u0e43\u0e0a\u0e48\u0e23\u0e49\u0e32\u0e19",
    "approx_city": "\u0e15\u0e33\u0e41\u0e2b\u0e19\u0e48\u0e07\u0e42\u0e14\u0e22\u0e1b\u0e23\u0e30\u0e21\u0e32\u0e13 (\u0e23\u0e30\u0e14\u0e31\u0e1a\u0e40\u0e21\u0e37\u0e2d\u0e07)",
    "approx_city_cap": "\u0e44\u0e21\u0e48\u0e21\u0e35\u0e1e\u0e34\u0e01\u0e31\u0e14\u0e41\u0e25\u0e30\u0e44\u0e21\u0e48\u0e21\u0e35\u0e0a\u0e37\u0e48\u0e2d\u0e40\u0e02\u0e15 \u0e2b\u0e21\u0e38\u0e14\u0e2d\u0e22\u0e39\u0e48\u0e01\u0e25\u0e32\u0e07\u0e40\u0e21\u0e37\u0e2d\u0e07",
    "back_to": "\u0e01\u0e25\u0e31\u0e1a\u0e44\u0e1b{label}",
}

EXTRA["ru"] = {
    "tap_to_copy": "\u041d\u0430\u0436\u043c\u0438\u0442\u0435, \u0447\u0442\u043e\u0431\u044b \u0441\u043a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u0442\u044c",
    "listed_by": "\u0423\u043a\u0430\u0437\u0430\u043d\u043e \u0432",
    "no_map_position": "\u0423 \u044d\u0442\u043e\u0439 \u0442\u043e\u0447\u043a\u0438 \u043d\u0435\u0442 \u043f\u043e\u0437\u0438\u0446\u0438\u0438 \u043d\u0430 \u043a\u0430\u0440\u0442\u0435",
    "no_map_position_cap": "\u041e\u043f\u0443\u0431\u043b\u0438\u043a\u043e\u0432\u0430\u043d \u0442\u043e\u043b\u044c\u043a\u043e \u0430\u0434\u0440\u0435\u0441. \u0418\u0441\u043f\u043e\u043b\u044c\u0437\u0443\u0439\u0442\u0435 \u00ab\u041c\u0430\u0440\u0448\u0440\u0443\u0442\u00bb, \u0447\u0442\u043e\u0431\u044b \u043d\u0430\u0439\u0442\u0438.",
    "community_from": "\u0441\u043e\u043e\u0431\u0449\u0435\u0441\u0442\u0432\u043e {src}, \u0434\u0430\u043d\u043d\u044b\u0435 \u043c\u043e\u0433\u0443\u0442 \u0443\u0441\u0442\u0430\u0440\u0435\u0442\u044c{date}",
    "community_listings": "\u0441\u043e\u043e\u0431\u0449\u0435\u0441\u0442\u0432\u0430",
    "rechecked_community": "\u043f\u0435\u0440\u0435\u043f\u0440\u043e\u0432\u0435\u0440\u0435\u043d\u043e \u043d\u0430 {host}, \u0432\u0441\u0451 \u0435\u0449\u0451 \u0434\u0430\u043d\u043d\u044b\u0435 \u0441\u043e\u043e\u0431\u0449\u0435\u0441\u0442\u0432\u0430",
    "checked_operator": "\u0441\u0432\u0435\u0440\u0435\u043d\u043e \u0441 {host}",
    "checked_operator_generic": "\u0441\u0432\u0435\u0440\u0435\u043d\u043e \u0441 \u043e\u0444\u0438\u0446\u0438\u0430\u043b\u044c\u043d\u043e\u0439 \u0441\u0442\u0440\u0430\u043d\u0438\u0446\u0435\u0439 \u043e\u043f\u0435\u0440\u0430\u0442\u043e\u0440\u0430",
    "price_common": "\u0421\u0430\u043c\u0430\u044f \u0447\u0430\u0441\u0442\u0430\u044f \u0446\u0435\u043d\u0430 \u0441\u0440\u0435\u0434\u0438 {n} \u0430\u0432\u0442\u043e\u043c\u0430\u0442\u043e\u0432 \u0432 \u0441\u043f\u0438\u0441\u043a\u0435 \u0437\u0434\u0435\u0441\u044c.",
    "per_machine": "\u0417\u0430 \u0430\u0432\u0442\u043e\u043c\u0430\u0442, \u043a\u0430\u043a \u0432 \u0441\u043f\u0438\u0441\u043a\u0435.",
    "machine_list_no_counts": "\u0415\u0441\u0442\u044c \u0441\u043f\u0438\u0441\u043e\u043a \u0430\u0432\u0442\u043e\u043c\u0430\u0442\u043e\u0432, \u0431\u0435\u0437 \u043a\u043e\u043b\u0438\u0447\u0435\u0441\u0442\u0432\u0430 \u043a\u0430\u0431\u0438\u043d\u0435\u0442\u043e\u0432",
    "machine_list_no_counts_cap": (
        "\u0421\u043f\u0438\u0441\u043e\u043a \u0441\u043e\u043e\u0431\u0449\u0435\u0441\u0442\u0432\u0430 \u043d\u0430\u0437\u044b\u0432\u0430\u0435\u0442 \u0430\u0432\u0442\u043e\u043c\u0430\u0442\u044b \u043d\u0438\u0436\u0435, "
        "\u043d\u0435 \u0443\u043a\u0430\u0437\u044b\u0432\u0430\u044f \u0441\u043a\u043e\u043b\u044c\u043a\u043e \u043a\u0430\u0436\u0434\u043e\u0433\u043e; "
        "\u044d\u0442\u043e \u043d\u0438\u0436\u043d\u044f\u044f \u0433\u0440\u0430\u043d\u0438\u0446\u0430, \u0430 \u043d\u0435 \u0438\u043d\u0432\u0435\u043d\u0442\u0430\u0440\u0438\u0437\u0430\u0446\u0438\u044f."
    ),
    "cab_counts_unavailable": "\u041a\u043e\u043b\u0438\u0447\u0435\u0441\u0442\u0432\u043e \u043a\u0430\u0431\u0438\u043d\u0435\u0442\u043e\u0432 \u043d\u0435\u0434\u043e\u0441\u0442\u0443\u043f\u043d\u043e",
    "cab_counts_unavailable_cap": "\u0418\u0441\u0442\u043e\u0447\u043d\u0438\u043a\u0438 \u044d\u0442\u043e\u0439 \u0442\u043e\u0447\u043a\u0438 \u043d\u0435 \u043f\u0443\u0431\u043b\u0438\u043a\u0443\u044e\u0442 \u0447\u0438\u0441\u043b\u043e \u0430\u0432\u0442\u043e\u043c\u0430\u0442\u043e\u0432.",
    "approx_address": "\u041f\u043e\u0437\u0438\u0446\u0438\u044f \u043f\u043e \u0430\u0434\u0440\u0435\u0441\u0443",
    "approx_address_cap": "\u0412 \u0438\u0441\u0442\u043e\u0447\u043d\u0438\u043a\u0435 \u043d\u0435\u0442 \u043a\u043e\u043e\u0440\u0434\u0438\u043d\u0430\u0442; \u043f\u0438\u043d \u0433\u0435\u043e\u043a\u043e\u0434\u0438\u0440\u043e\u0432\u0430\u043d \u043f\u043e \u043d\u0430\u043f\u0435\u0447\u0430\u0442\u0430\u043d\u043d\u043e\u043c\u0443 \u0430\u0434\u0440\u0435\u0441\u0443.",
    "approx_street": "\u041f\u043e\u0437\u0438\u0446\u0438\u044f \u043f\u043e \u0430\u0434\u0440\u0435\u0441\u0443 (\u0443\u0440\u043e\u0432\u0435\u043d\u044c \u0443\u043b\u0438\u0446\u044b)",
    "approx_street_cap": "\u0413\u0435\u043e\u043a\u043e\u0434\u0438\u0440\u043e\u0432\u0430\u043d\u043e \u0434\u043e \u0443\u043b\u0438\u0446\u044b, \u043d\u0435 \u0434\u043e \u0437\u0434\u0430\u043d\u0438\u044f; \u043c\u043e\u0436\u0435\u0442 \u043e\u0448\u0438\u0431\u0438\u0442\u044c\u0441\u044f \u043d\u0430 \u043e\u0434\u043d\u0443-\u0434\u0432\u0435 \u0434\u0432\u0435\u0440\u0438.",
    "approx_district": "\u041f\u0440\u0438\u0431\u043b\u0438\u0437\u0438\u0442\u0435\u043b\u044c\u043d\u0430\u044f \u043f\u043e\u0437\u0438\u0446\u0438\u044f (\u0440\u0430\u0439\u043e\u043d)",
    "approx_district_cap": "\u0411\u0435\u0437 \u043a\u043e\u043e\u0440\u0434\u0438\u043d\u0430\u0442; \u043f\u0438\u043d \u2014 \u0446\u0435\u043d\u0442\u0440 \u0440\u0430\u0439\u043e\u043d\u0430 \u0438\u0437 \u0430\u0434\u0440\u0435\u0441\u0430, \u043d\u0435 \u0441\u0430\u043c \u0437\u0430\u043b.",
    "approx_city": "\u041f\u0440\u0438\u0431\u043b\u0438\u0437\u0438\u0442\u0435\u043b\u044c\u043d\u0430\u044f \u043f\u043e\u0437\u0438\u0446\u0438\u044f (\u0433\u043e\u0440\u043e\u0434)",
    "approx_city_cap": "\u0411\u0435\u0437 \u043a\u043e\u043e\u0440\u0434\u0438\u043d\u0430\u0442 \u0438 \u0431\u0435\u0437 \u043d\u0430\u0437\u0432\u0430\u043d\u0438\u044f \u0440\u0430\u0439\u043e\u043d\u0430; \u043f\u0438\u043d \u2014 \u0446\u0435\u043d\u0442\u0440 \u0433\u043e\u0440\u043e\u0434\u0430.",
    "back_to": "\u041d\u0430\u0437\u0430\u0434 \u043a {label}",
}

p = Path(__file__).with_name("place_extra_seed.json")
p.write_text(json.dumps(EXTRA, ensure_ascii=False, indent=2), encoding="utf-8")
print("langs", sorted(EXTRA.keys()))
