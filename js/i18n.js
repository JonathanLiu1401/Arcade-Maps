/* Arcade Maps - UI language (i18n).

   Self-contained: nested string dicts, browser detect on first visit, localStorage
   key am_lang, AM.i18n.t(key) / data-i18n attributes, and the top-right language
   button (inserted by settings.js before the gear).

   Missing keys fall back to English, then the key itself. Game brand names are
   never translated. Country names in data stay English for now. */
window.AM = window.AM || {};

(function (AM) {
  "use strict";

  var STORAGE_KEY = "am_lang";

  /* Menu order: locales covering regions with many arcades first. */
  var LANGS = [
    { code: "en", native: "English" },
    { code: "zh-Hans", native: "\u7b80\u4f53\u4e2d\u6587" },
    { code: "zh-Hant", native: "\u7e41\u9ad4\u4e2d\u6587" },
    { code: "ja", native: "\u65e5\u672c\u8a9e" },
    { code: "ko", native: "\ud55c\uad6d\uc5b4" },
    { code: "id", native: "Bahasa Indonesia" },
    { code: "ms", native: "Bahasa Melayu" },
    { code: "th", native: "\u0e44\u0e17\u0e22" },
    { code: "vi", native: "Ti\u1ebfng Vi\u1ec7t" },
    { code: "fil", native: "Filipino" },
    { code: "es", native: "Espa\u00f1ol" },
    { code: "fr", native: "Fran\u00e7ais" },
    { code: "de", native: "Deutsch" },
    { code: "pt", native: "Portugu\u00eas" },
    { code: "it", native: "Italiano" },
    { code: "ru", native: "\u0420\u0443\u0441\u0441\u043a\u0438\u0439" }
  ];

  var CODE_SET = {};
  LANGS.forEach(function (L) { CODE_SET[L.code] = true; });

  /* Nested dicts. dig() walks "a.b.c". */
  var STRINGS = {
    en: {
      app: {
        title: "Arcade Maps",
        updated: "updated {date}",
        data_failed: "data load failed"
      },
      drawer: {
        toggle: "Toggle filters",
        toggle_title: "Toggle filter panel"
      },
      meta: {
        updated_title: "Data last updated",
        count_title: "Markers shown / plottable stores"
      },
      search: {
        placeholder: "Search name or address...",
        aria: "Search arcades by name or address"
      },
      repo: {
        title: "GitHub repository",
        aria: "GitHub repository"
      },
      tab: {
        filters: "Filters",
        china: "No-coords list"
      },
      pane: {
        games: "Games",
        cab_variants: "Cab variants",
        arcade_size: "Arcade size"
      },
      btn: {
        all: "all",
        none: "none"
      },
      hint: {
        cab_variant: "Checking a variant restricts that game's markers to stores with the cab.",
        arcade_size: "Cabinet count bands match the map marker shapes. Unknown means no trusted count was published.",
        china1: "Stores without map coordinates (mostly China).",
        china2: "These come from the official WAHLAP list and the BemaniCN community map, which publish addresses only; search the address in your preferred map app. Chinese web maps use shifted coordinates (GCJ-02); plotted China points were converted to WGS-84 - positions are approximate."
      },
      nearby: {
        title: "Nearby arcades",
        close: "close",
        close_aria: "Close nearby list",
        pane_aria: "Nearby arcades",
        search_area: "Search this area",
        empty: "No stores match the current filters. Turn a game or a source back on to see nearby results.",
        nearest_you: "Nearest to your location",
        nearest_to: "Nearest to {label}",
        showing: "Showing the {n} nearest stores that match your filters. Stores without coordinates are not shown.",
        no_coords_note: "Stores without coordinates are not shown.",
        locate: "Show arcades near me",
        your_location: "your location",
        this_point: "this point"
      },
      map: {
        aria: "Arcade map"
      },
      empty: {
        map: "No arcades match your filters"
      },
      foot: {
        data_sources: "data sources",
        sources: "sources",
        show: "Show data source counts",
        hide: "Hide data source counts"
      },
      lang: {
        button: "Language",
        menu: "Choose language"
      },
      settings: {
        title: "Settings",
        close: "Close settings",
        sections: "Settings sections",
        gear: "Settings",
        sec_sources: "Sources",
        sec_display: "Display",
        sec_location: "Location",
        sec_about: "About",
        sources_head: "Data sources",
        sources_note: "Turn a source off to hide its stores. A store listed by more than one source stays on the map while any of them is on.",
        display_head: "Display",
        marker_scaling: "Marker size by cabinet count",
        marker_scaling_desc: "Draw busier stores as larger icons. Turn it off to draw every marker the same size - the icon shape still shows the tier.",
        location_head: "Location",
        location_enabled: "Enable location features",
        location_enabled_desc: "Show the locate button and the list of arcades nearest to you.",
        location_privacy: "Your location never leaves the browser.",
        location_privacy_body: " It is read only after you ask for it, used on this page to sort stores by distance, and is never uploaded, stored or shared. This site has no server and no analytics.",
        legend: "Legend",
        icon_cabinets: "Icon: total cabinets at the store",
        tier_unknown: "Count unknown (drawn mid-size)",
        cluster_note: "Cluster of 12 stores. A gold rim means at least one 20+ cabinet store is inside.",
        legend_note: "Each tier is a different shape, so the tier reads without comparing sizes. Most official listings publish which games a store has but not how many cabinets, so an unknown count gets its own icon at mid weight rather than the smallest one - it means \"not published\", never \"one cabinet\". Counts come from BemaniCN and, where they are more than a bare presence marker, from ZIv. Sizes follow the Display setting; the shapes do not.",
        icon_color: "Icon colour: game at the store",
        color_note: "A store with several games takes the colour of the first selected game it has, in the order below. The tier icons above are all drawn in one sample colour; on the map each takes its store's game colour.",
        badges: "Badges in a store popup",
        cab_badge: "Yellow badges name the CABINET, not the game: Lightning model IIDX, Valkyrie or NEMSYS SOUND VOLTEX, DDR gold and Universal cabs, GITADORA Arena, pop'n Pikapika, and Taiko regional builds. The cabinet decides which charts and modes you can actually play.",
        dead_badge: "A struck-through badge is an OFFLINE cabinet: maimai FiNALE and pre-LCD DDR cabs still run, but their networks shut down, so nothing is saved - no scores, no unlocks, no online play.",
        badge_note: "Where cabinet data comes from, and what it cannot tell you. Official operator listings publish cabinet models for Japan only, so outside Japan the model is read from the machine list community members wrote. That means a missing badge always reads as \"nobody recorded the model\" and never as \"standard cabinet\". Two known gaps: the operator feed for SOUND VOLTEX returns the same stores whether or not you ask for Valkyrie cabs, so Valkyrie is taken from community listings alone; and CHUNITHM gold and silver cabinets are real (gold runs at 120Hz, and the two do not match against each other in versus) but no source publishes which a store has, so this map does not guess.",
        about_map: "About this map",
        stats: "{stores} stores, {plottable} with coordinates. Data updated {updated}.",
        link_source: "Source code on GitHub",
        link_data: "Data sources",
        link_license: "MIT licence",
        osm_note: "Map data (c) OpenStreetMap contributors, ODbL. Store listings belong to their respective sources and are aggregated here for convenience. Chinese coordinates are converted from GCJ-02 and are approximate.",
        shown: "{n} of {total} mappable stores shown with the current filters.",
        src_extra: "Additional data source.",
        src_count_title: "stores from this source, including entries without coordinates"
      },
      legend: {
        toggle: "Legend",
        icon_cabinets: "Icon: cabinets at the store",
        color_game: "Colour: game",
        full: "Full legend in Settings",
        unknown_title: "count unknown, drawn mid-size"
      },
      src: {
        allnet_name: "ALL.Net",
        allnet_desc: "Official SEGA store locator: maimai DX, CHUNITHM, O.N.G.E.K.I.",
        eagate_name: "e-amusement",
        eagate_desc: "Official KONAMI store locator: IIDX, SOUND VOLTEX, DDR and other Bemani.",
        wahlap_name: "WAHLAP",
        wahlap_desc: "Official SEGA distributor for mainland China. Addresses only, no coordinates.",
        bemanicn_name: "BemaniCN",
        bemanicn_desc: "Community-run map of Bemani cabinets in mainland China.",
        ziv_name: "Zenius-I-Vanisher",
        ziv_desc: "Community arcade database with worldwide coverage.",
        round1usa_name: "Round1 USA",
        round1usa_desc: "Official Round1 venue list for the United States.",
        community_name: "Community",
        community_desc: "Entries curated by hand in this repository."
      },
      place: {
        directions: "Directions",
        nearby: "Nearby",
        share: "Share",
        filters: "Filters",
        close: "Close place details",
        details: "Place details",
        address_copied: "Address copied",
        link_copied: "Link copied",
        copy_failed: "Copy failed",
        tap_to_copy: "Tap to copy",
        listed_by: "Listed by",
        no_map_position: "No map position for this store",
        no_map_position_cap: "Published as an address only. Use Directions to search it.",
        community_from: "community data from {src}, may be outdated{date}",
        community_listings: "community listings",
        rechecked_community: "re-checked on {host}, still community data",
        checked_operator: "checked against {host}",
        checked_operator_generic: "checked against the operator own listing",
        price_common: "Most common price across {n} listed machines here.",
        per_machine: "Per machine, as listed.",
        machine_list_no_counts: "Machine list, but no cab counts",
        machine_list_no_counts_cap: "The community listing names the machines below without saying how many of each, so the list is a floor and not a tally.",
        cab_counts_unavailable: "Cab counts unavailable",
        cab_counts_unavailable_cap: "The listings this store comes from do not publish how many machines it has.",
        approx_address: "Position from the address",
        approx_address_cap: "The source publishes no coordinates, so this pin was geocoded from the printed address.",
        approx_street: "Position from the address - street level",
        approx_street_cap: "Geocoded to the road rather than the building, so expect to be a door or two out.",
        approx_district: "Position approximate - district level",
        approx_district_cap: "The source publishes no coordinates, so this pin is the centre of the district named in the address, not the store.",
        approx_city: "Position approximate - city level",
        approx_city_cap: "The source publishes no coordinates and the address names no district, so this pin is the centre of the city.",
        back_to: "Back to {label}",
        search_gmaps: "Search in Google Maps",
      },
      nb: {
        err_denied: "Location permission was denied. Allow it for this site in your browser settings, then try again.",
        err_unavailable: "Your location is not available right now. Try again, or search for a city instead.",
        err_timeout: "Getting your location took too long. Try again.",
        err_generic: "Could not get your location.",
        err_empty: "Your location came back empty. Try again in a moment.",
        err_off: "Location is switched off in settings.",
        err_https: "Location needs a secure (https) connection.",
        err_unsupported: "This browser cannot report your location."
      },
      cabs: {
        sdvx_vm: "Valkyrie model",
        iidx_lm: "Lightning model",
        ddr_gold: "Gold cab (20th anniv.)",
        gitadora_arena: "Arena model",
        popn_pikapika: "Pikapika model",
        maimai_classic: "maimai FiNALE / pre-DX",
        sdvx_nemsys: "NEMSYS (standard)",
        ddr_universal: "Universal Model (EU/NA)",
        ddr_legacy: "Legacy CRT cabinet",
        other_game: "Other",
      },
      ui: {
        shown: "{n} shown",
        stores_total: "{n} stores total",
        per_credit: "per credit",
        show_more: "Show more",
        show_less: "Show less",
        search_wide: "Search games, arcades, places...",
        search_narrow: "Search...",
        cab_model_unpublished: "Cabinet model not published",
        cab_model_unpublished_cap: "No listing says which cabinet this store runs. Official cab data covers Japan only, and community listings record the model just when someone noted it - so this is \"unknown\", not \"standard\".",
        offline_cab: "offline cabinet",
        offline_cabs: "offline cabinets",
        offline_cap: "This cabinet's network has shut down. It can still be played, but nothing is saved: no score history, no online play, no unlocks.",
        price_median: "{game}, median of {n} quoted prices in {country}. Not this store's own price.",
        price_sparse: "Based on only {n} listing(s) in {country}{for_game}, so treat it as a rough guide.",
        for_game: " for {game}",
        typical_country: "Typical for {country} - not this store's own price",
        permanently_closed: "Permanently closed.",
        source: "source",
        photo_by: "photo: {credit}",
        unknown_author: "unknown",
        listed: "listed",
        size_1: "1 to 2 cabinets",
        size_2: "3 to 9 cabinets",
        size_3: "10 to 19 cabinets",
        size_4: "20 to 49 cabinets",
        size_5: "50 or more cabinets (mega arcade)",
        size_U: "Count unknown",
      }
    },

    "zh-Hans": {
      app: { title: "街机地图", updated: "更新于 {date}", data_failed: "数据加载失败" },
      drawer: { toggle: "切换筛选", toggle_title: "切换筛选面板" },
      meta: { updated_title: "数据最后更新", count_title: "显示标记 / 可绘制门店" },
      search: { placeholder: "搜索名称或地址...", aria: "按名称或地址搜索街机厅" },
      repo: { title: "GitHub 仓库", aria: "GitHub 仓库" },
      tab: { filters: "筛选", china: "无坐标列表" },
      pane: { games: "游戏", cab_variants: "机台型号",
        arcade_size: "街机规模" },
      btn: { all: "全选", none: "全不选" },
      hint: {
        cab_variant: "勾选型号后，仅显示拥有该机台的门店标记。",
        arcade_size: "机台数量分档与地图标记形状一致。未知表示没有可信的已公布数量。",
        china1: "没有地图坐标的门店（多为中国大陆）。",
        china2: "这些数据来自官方 WAHLAP 列表与 BemaniCN 社区地图，仅提供地址；请在地图应用中搜索地址。中国网络地图使用偏移坐标（GCJ-02）；图上已绘制的中国点已转换为 WGS-84，位置为近似值。"
      },
      nearby: {
        title: "附近街机厅", close: "关闭", close_aria: "关闭附近列表", pane_aria: "附近街机厅",
        search_area: "搜索此区域", empty: "当前筛选下没有匹配门店。请重新打开某个游戏或数据源。",
        nearest_you: "距离你最近", nearest_to: "距离 {label} 最近",
        showing: "显示符合筛选的最近 {n} 家门店。无坐标门店不显示。",
        no_coords_note: "无坐标门店不显示。", locate: "显示我附近的街机厅",
        your_location: "你的位置", this_point: "此点"
      },
      map: { aria: "街机地图" },
      empty: { map: "没有符合筛选条件的街机厅" },
      foot: { data_sources: "数据来源", sources: "来源", show: "显示数据源统计", hide: "隐藏数据源统计" },
      lang: { button: "语言", menu: "选择语言" },
      settings: {
        title: "设置", close: "关闭设置", sections: "设置分区", gear: "设置",
        sec_sources: "数据源", sec_display: "显示", sec_location: "定位", sec_about: "关于",
        sources_head: "数据来源",
        sources_note: "关闭某个来源可隐藏其门店。被多个来源收录的门店，只要任一来源开启就会显示。",
        display_head: "显示",
        marker_scaling: "按机台数量缩放标记",
        marker_scaling_desc: "机台更多的门店图标更大。关闭后所有标记同尺寸，形状仍表示档位。",
        location_head: "定位",
        location_enabled: "启用定位功能",
        location_enabled_desc: "显示定位按钮以及离你最近的街机厅列表。",
        location_privacy: "你的位置不会离开浏览器。",
        location_privacy_body: " 仅在你主动请求后读取，用于本页按距离排序，绝不会上传、存储或分享。本站无服务器、无分析统计。",
        legend: "图例",
        icon_cabinets: "图标：门店机台总数",
        tier_unknown: "数量未知（中等尺寸绘制）",
        cluster_note: "包含 12 家门店的聚合。金色描边表示其中至少有一家 20+ 机台门店。",
        legend_note: "每个档位使用不同形状，无需比大小也能读懂。多数官方列表公布游戏但不公布机台数量，因此未知数量使用独立的中等权重图标，表示“未公布”而非“一台”。数量来自 BemaniCN，以及在有实质数据时来自 ZIv。尺寸跟随显示设置；形状不变。",
        icon_color: "图标颜色：门店游戏",
        color_note: "多家游戏的门店取下方顺序中第一个已选中游戏的颜色。上方图例用统一示例色；地图上按门店游戏着色。",
        badges: "门店弹窗中的徽章",
        cab_badge: "黄色徽章表示机台型号而非游戏：Lightning 版 IIDX、Valkyrie 或 NEMSYS SOUND VOLTEX、DDR 金色与 Universal 机台、GITADORA Arena、pop'n ピカピカ、以及太鼓地区版本。机台决定你能玩哪些谱面与模式。",
        dead_badge: "带删除线的徽章是离线机台：maimai FiNALE 与前 LCD 的 DDR 仍可游玩，但网络已关闭，无法存分、解锁或联机。",
        badge_note: "机台数据来源与局限。官方运营商仅公布日本机型；日本以外来自社区机台列表。缺失徽章表示“无人记录型号”，而非“标准机台”。已知缺口：SOUND VOLTEX 运营商接口无论是否筛选 Valkyrie 都返回相同门店，故 Valkyrie 仅来自社区；CHUNITHM 金/银框真实存在（金框 120Hz，且对战不互通），但无来源公布具体型号，本图不猜测。",
        about_map: "关于本图",
        stats: "{stores} 家门店，其中 {plottable} 家有坐标。数据更新于 {updated}。",
        link_source: "GitHub 源代码", link_data: "数据来源", link_license: "MIT 许可",
        osm_note: "地图数据 (c) OpenStreetMap 贡献者，ODbL。门店列表归各自来源所有，此处仅为汇总。中国坐标由 GCJ-02 转换，为近似值。",
        shown: "当前筛选下显示 {n} / {total} 家可绘制门店。",
        src_extra: "其他数据来源。",
        src_count_title: "该来源门店数，含无坐标条目"
      },
      legend: {
        toggle: "图例", icon_cabinets: "图标：门店机台数", color_game: "颜色：游戏",
        full: "设置中查看完整图例", unknown_title: "数量未知，中等尺寸"
      },
      src: {
        allnet_name: "ALL.Net", allnet_desc: "SEGA 官方门店检索：maimai DX、CHUNITHM、O.N.G.E.K.I.",
        eagate_name: "e-amusement", eagate_desc: "KONAMI 官方门店检索：IIDX、SOUND VOLTEX、DDR 及其他 Bemani。",
        wahlap_name: "WAHLAP", wahlap_desc: "中国大陆 SEGA 官方代理。仅有地址，无坐标。",
        bemanicn_name: "BemaniCN", bemanicn_desc: "中国大陆 Bemani 机台社区地图。",
        ziv_name: "Zenius-I-Vanisher", ziv_desc: "覆盖全球的社区街机数据库。",
        round1usa_name: "Round1 USA", round1usa_desc: "美国 Round1 官方门店列表。",
        community_name: "Community", community_desc: "本仓库手工整理的条目。"
      },
      place: {
        directions: "路线", nearby: "附近", share: "分享", filters: "筛选",
        close: "关闭门店详情", details: "门店详情",
        address_copied: "地址已复制", link_copied: "链接已复制", copy_failed: "复制失败",
        tap_to_copy: "点按复制",
        listed_by: "收录来源",
        no_map_position: "此门店没有地图位置",
        no_map_position_cap: "来源仅公布了地址。请用「路线」搜索。",
        community_from: "社区数据（{src}），可能过时{date}",
        community_listings: "社区列表",
        rechecked_community: "已在 {host} 复核，仍为社区数据",
        checked_operator: "已对照 {host} 核实",
        checked_operator_generic: "已对照运营商官方页面核实",
        price_common: "此处列出的 {n} 台机台中最常见价格。",
        per_machine: "按列表中每台机台计。",
        machine_list_no_counts: "有机台列表，但无台数",
        machine_list_no_counts_cap: "社区列表写了下列机种，但未说明各有几台，因此只是下限而非盘点。",
        cab_counts_unavailable: "无法获得机台数量",
        cab_counts_unavailable_cap: "收录此门店的列表未公布机台数量。",
        approx_address: "位置来自地址",
        approx_address_cap: "来源未公布坐标，图钉由印刷地址地理编码得到。",
        approx_street: "位置来自地址（街道级）",
        approx_street_cap: "定位到道路而非建筑，可能偏差一两扇门。",
        approx_district: "位置近似（区县级）",
        approx_district_cap: "来源未公布坐标，图钉为地址中区县的中心，而非门店。",
        approx_city: "位置近似（城市级）",
        approx_city_cap: "来源未公布坐标且地址无名区县，图钉为城市中心。",
        back_to: "返回{label}",
        search_gmaps: "在 Google 地图中搜索",
      },
      nb: {
        err_denied: "定位权限被拒绝。请在浏览器设置中允许本站定位后重试。",
        err_unavailable: "暂时无法获取位置。请重试，或搜索城市。",
        err_timeout: "定位超时。请重试。",
        err_generic: "无法获取你的位置。",
        err_empty: "位置结果为空。请稍后再试。",
        err_off: "设置中已关闭定位功能。",
        err_https: "定位需要安全（https）连接。",
        err_unsupported: "此浏览器无法报告位置。"
      },
      cabs: {
        sdvx_vm: "Valkyrie 机型",
        iidx_lm: "Lightning 机型",
        ddr_gold: "金色机台（20周年）",
        gitadora_arena: "Arena 机型",
        popn_pikapika: "皮卡皮卡机型",
        maimai_classic: "maimai FiNALE / 旧机台",
        sdvx_nemsys: "NEMSYS（标准）",
        ddr_universal: "Universal Model（欧美）",
        ddr_legacy: "旧式 CRT 机台",
        other_game: "其他",
      },
      ui: {
        shown: "{n} 个显示",
        stores_total: "共 {n} 家门店",
        per_credit: "每次投币",
        show_more: "展开更多",
        show_less: "收起",
        search_wide: "搜索游戏、街机厅、地点...",
        search_narrow: "搜索...",
        cab_model_unpublished: "未公布机台型号",
        cab_model_unpublished_cap: "没有来源说明此店运行哪种机台。官方机台数据仅覆盖日本；社区列表只在有人记录时才有型号。因此是「未知」而非「标准」。",
        offline_cab: "离线机台",
        offline_cabs: "离线机台",
        offline_cap: "此机台网络已关闭。仍可玩，但不会保存分数、联机或解锁。",
        price_median: "{game}，{country} {n} 条报价的中位数。非本店实际价格。",
        price_sparse: "仅基于 {country} 的 {n} 条信息{for_game}，仅供参考。",
        for_game: "（{game}）",
        typical_country: "{country} 典型价 - 非本店实际价格",
        permanently_closed: "已永久关闭。",
        source: "来源",
        photo_by: "照片: {credit}",
        unknown_author: "未知",
        listed: "已登记",
        size_1: "1–2 台机台",
        size_2: "3–9 台",
        size_3: "10–19 台",
        size_4: "20–49 台",
        size_5: "50 台以上（超大店）",
        size_U: "台数未知",
      }
    },

    "zh-Hant": {
      app: { title: "街機地圖", updated: "更新於 {date}", data_failed: "資料載入失敗" },
      drawer: { toggle: "切換篩選", toggle_title: "切換篩選面板" },
      meta: { updated_title: "資料最後更新", count_title: "顯示標記 / 可繪製店家" },
      search: { placeholder: "搜尋名稱或地址...", aria: "依名稱或地址搜尋街機廳" },
      repo: { title: "GitHub 儲存庫", aria: "GitHub 儲存庫" },
      tab: { filters: "篩選", china: "無座標列表" },
      pane: { games: "遊戲", cab_variants: "機台型號",
        arcade_size: "街機規模" },
      btn: { all: "全選", none: "全不選" },
      hint: {
        cab_variant: "勾選型號後，僅顯示擁有該機台的店家標記。",
        arcade_size: "機台數量分檔與地圖標記形狀一致。未知表示沒有可信的已公布數量。",
        china1: "沒有地圖座標的店家（多為中國大陸）。",
        china2: "這些資料來自官方 WAHLAP 列表與 BemaniCN 社群地圖，僅提供地址；請在地圖應用中搜尋地址。中國網路地圖使用偏移座標（GCJ-02）；圖上已繪製的中國點已轉換為 WGS-84，位置為近似值。"
      },
      nearby: {
        title: "附近街機廳", close: "關閉", close_aria: "關閉附近列表", pane_aria: "附近街機廳",
        search_area: "搜尋此區域", empty: "目前篩選下沒有符合店家。請重新開啟某個遊戲或資料來源。",
        nearest_you: "距離你最近", nearest_to: "距離 {label} 最近",
        showing: "顯示符合篩選的最近 {n} 家店家。無座標店家不顯示。",
        no_coords_note: "無座標店家不顯示。", locate: "顯示我附近的街機廳",
        your_location: "你的位置", this_point: "此點"
      },
      map: { aria: "街機地圖" },
      empty: { map: "沒有符合篩選條件的街機廳" },
      foot: { data_sources: "資料來源", sources: "來源", show: "顯示資料來源統計", hide: "隱藏資料來源統計" },
      lang: { button: "語言", menu: "選擇語言" },
      settings: {
        title: "設定", close: "關閉設定", sections: "設定分區", gear: "設定",
        sec_sources: "資料來源", sec_display: "顯示", sec_location: "定位", sec_about: "關於",
        sources_head: "資料來源",
        sources_note: "關閉某個來源可隱藏其店家。被多個來源收錄的店家，只要任一來源開啟就會顯示。",
        display_head: "顯示",
        marker_scaling: "依機台數量縮放標記",
        marker_scaling_desc: "機台較多的店家圖示較大。關閉後所有標記同尺寸，形狀仍表示檔位。",
        location_head: "定位",
        location_enabled: "啟用定位功能",
        location_enabled_desc: "顯示定位按鈕以及離你最近的街機廳列表。",
        location_privacy: "你的位置不會離開瀏覽器。",
        location_privacy_body: " 僅在你主動請求後讀取，用於本頁依距離排序，絕不會上傳、儲存或分享。本站無伺服器、無分析統計。",
        legend: "圖例",
        icon_cabinets: "圖示：店家機台總數",
        tier_unknown: "數量未知（中等尺寸繪製）",
        cluster_note: "包含 12 家店家的聚合。金色描邊表示其中至少有一家 20+ 機台店家。",
        legend_note: "每個檔位使用不同形狀，無需比大小也能讀懂。多數官方列表公布遊戲但不公布機台數量，因此未知數量使用獨立的中等權重圖示，表示「未公布」而非「一台」。數量來自 BemaniCN，以及在有實質資料時來自 ZIv。尺寸跟隨顯示設定；形狀不變。",
        icon_color: "圖示顏色：店家遊戲",
        color_note: "多家遊戲的店家取下方順序中第一個已選中遊戲的顏色。上方圖例用統一示例色；地圖上依店家遊戲著色。",
        badges: "店家彈窗中的徽章",
        cab_badge: "黃色徽章表示機台型號而非遊戲：Lightning 版 IIDX、Valkyrie 或 NEMSYS SOUND VOLTEX、DDR 金色與 Universal 機台、GITADORA Arena、pop'n ピカピカ、以及太鼓地區版本。機台決定你能玩哪些譜面與模式。",
        dead_badge: "帶刪除線的徽章是離線機台：maimai FiNALE 與前 LCD 的 DDR 仍可遊玩，但網路已關閉，無法存分、解鎖或連線。",
        badge_note: "機台資料來源與局限。官方營運商僅公布日本機型；日本以外來自社群機台列表。缺失徽章表示「無人記錄型號」，而非「標準機台」。已知缺口：SOUND VOLTEX 營運商介面無論是否篩選 Valkyrie 都回傳相同店家，故 Valkyrie 僅來自社群；CHUNITHM 金/銀框真實存在，但無來源公布具體型號，本圖不猜測。",
        about_map: "關於本地圖",
        stats: "{stores} 家店家，其中 {plottable} 家有座標。資料更新於 {updated}。",
        link_source: "GitHub 原始碼", link_data: "資料來源", link_license: "MIT 授權",
        osm_note: "地圖資料 (c) OpenStreetMap 貢獻者，ODbL。店家列表歸各自來源所有，此處僅為彙總。中國座標由 GCJ-02 轉換，為近似值。",
        shown: "目前篩選下顯示 {n} / {total} 家可繪製店家。",
        src_extra: "其他資料來源。",
        src_count_title: "該來源店家數，含無座標條目"
      },
      legend: {
        toggle: "圖例", icon_cabinets: "圖示：店家機台數", color_game: "顏色：遊戲",
        full: "設定中查看完整圖例", unknown_title: "數量未知，中等尺寸"
      },
      src: {
        allnet_name: "ALL.Net", allnet_desc: "SEGA 官方店家檢索：maimai DX、CHUNITHM、O.N.G.E.K.I.",
        eagate_name: "e-amusement", eagate_desc: "KONAMI 官方店家檢索：IIDX、SOUND VOLTEX、DDR 及其他 Bemani。",
        wahlap_name: "WAHLAP", wahlap_desc: "中國大陸 SEGA 官方代理。僅有地址，無座標。",
        bemanicn_name: "BemaniCN", bemanicn_desc: "中國大陸 Bemani 機台社群地圖。",
        ziv_name: "Zenius-I-Vanisher", ziv_desc: "涵蓋全球的社群街機資料庫。",
        round1usa_name: "Round1 USA", round1usa_desc: "美國 Round1 官方店家列表。",
        community_name: "Community", community_desc: "本儲存庫手工整理的條目。"
      },
      place: {
        directions: "路線", nearby: "附近", share: "分享", filters: "篩選",
        close: "關閉店家詳情", details: "店家詳情",
        address_copied: "地址已複製", link_copied: "連結已複製", copy_failed: "複製失敗",
        tap_to_copy: "點按複製",
        listed_by: "收錄來源",
        no_map_position: "此店舖沒有地圖位置",
        no_map_position_cap: "來源僅公佈了地址。請用「路線」搜尋。",
        community_from: "社群資料（{src}），可能過時{date}",
        community_listings: "社群列表",
        rechecked_community: "已在 {host} 複核，仍為社群資料",
        checked_operator: "已對照 {host} 核實",
        checked_operator_generic: "已對照營運商官方頁面核實",
        price_common: "此處列出的 {n} 台機台中最常見價格。",
        per_machine: "按列表中每台機台計。",
        machine_list_no_counts: "有機台列表，但無台數",
        machine_list_no_counts_cap: "社群列表寫了下列機種，但未說明各有幾台，因此只是下限而非盤點。",
        cab_counts_unavailable: "無法取得機台數量",
        cab_counts_unavailable_cap: "收錄此店舖的列表未公佈機台數量。",
        approx_address: "位置來自地址",
        approx_address_cap: "來源未公佈座標，圖釘由印刷地址地理編碼得到。",
        approx_street: "位置來自地址（街道級）",
        approx_street_cap: "定位到道路而非建築，可能偏差一兩扇門。",
        approx_district: "位置近似（區縣級）",
        approx_district_cap: "來源未公佈座標，圖釘為地址中區縣的中心，而非店舖。",
        approx_city: "位置近似（城市級）",
        approx_city_cap: "來源未公佈座標且地址無名區縣，圖釘為城市中心。",
        back_to: "返回{label}",
        search_gmaps: "在 Google 地圖中搜尋",
      },
      nb: {
        err_denied: "定位權限被拒絕。請在瀏覽器設定中允許本站定位後重試。",
        err_unavailable: "暫時無法取得位置。請重試，或搜尋城市。",
        err_timeout: "定位逾時。請重試。",
        err_generic: "無法取得你的位置。",
        err_empty: "位置結果為空。請稍後再試。",
        err_off: "設定中已關閉定位功能。",
        err_https: "定位需要安全（https）連線。",
        err_unsupported: "此瀏覽器無法回報位置。"
      },
      cabs: {
        sdvx_vm: "Valkyrie 機型",
        iidx_lm: "Lightning 機型",
        ddr_gold: "金色機台（20週年）",
        gitadora_arena: "Arena 機型",
        popn_pikapika: "皮卡皮卡機型",
        maimai_classic: "maimai FiNALE / 舊機台",
        sdvx_nemsys: "NEMSYS（標準）",
        ddr_universal: "Universal Model（歐美）",
        ddr_legacy: "舊式 CRT 機台",
        other_game: "其他",
      },
      ui: {
        shown: "{n} 個顯示",
        stores_total: "共 {n} 家店",
        per_credit: "每次投幣",
        show_more: "展開更多",
        show_less: "收起",
        search_wide: "搜尋遊戲、街機廳、地點...",
        search_narrow: "搜索...",
        cab_model_unpublished: "未公佈機台型號",
        cab_model_unpublished_cap: "沒有來源說明此店運行哪種機台。官方機台資料僅覆蓋日本；社群列表只在有人記錄時才有型號。因此是「未知」而非「標準」。",
        offline_cab: "離線機台",
        offline_cabs: "離線機台",
        offline_cap: "此機台網絡已關閉。仍可玩，但不會保存分數、聯機或解鎖。",
        price_median: "{game}，{country} {n} 條報價的中位數。非本店實際價格。",
        price_sparse: "僅基於 {country} 的 {n} 條資訊{for_game}，僅供參考。",
        for_game: "（{game}）",
        typical_country: "{country} 典型價 - 非本店實際價格",
        permanently_closed: "已永久關閉。",
        source: "來源",
        photo_by: "照片: {credit}",
        unknown_author: "未知",
        listed: "已登記",
        size_1: "1–2 台機台",
        size_2: "3–9 台",
        size_3: "10–19 台",
        size_4: "20–49 台",
        size_5: "50 台以上（超大店）",
        size_U: "台數未知",
      }
    },

    ja: {
      app: { title: "アーケードマップ", updated: "更新 {date}", data_failed: "データの読み込みに失敗" },
      drawer: { toggle: "フィルター切替", toggle_title: "フィルターパネルを切替" },
      meta: { updated_title: "データ最終更新", count_title: "表示マーカー / 地図上の店舗" },
      search: { placeholder: "店名または住所で検索...", aria: "店名または住所でアーケードを検索" },
      repo: { title: "GitHub リポジトリ", aria: "GitHub リポジトリ" },
      tab: { filters: "フィルター", china: "座標なし一覧" },
      pane: { games: "ゲーム", cab_variants: "筐体バリエーション",
        arcade_size: "アーケード規模" },
      btn: { all: "すべて", none: "なし" },
      hint: {
        cab_variant: "バリエーションを選ぶと、その筐体がある店舗のマーカーだけに絞られます。",
        arcade_size: "筐体数の帯は地図マーカーの形と一致します。不明は信頼できる公開数が無いことを意味します。",
        china1: "地図座標のない店舗（主に中国）。",
        china2: "公式 WAHLAP リストと BemaniCN コミュニティ地図の住所のみのデータです。地図アプリで住所を検索してください。中国のウェブ地図は GCJ-02 を使用；地図上の中国地点は WGS-84 に変換済みで、位置は概算です。"
      },
      nearby: {
        title: "近くのアーケード", close: "閉じる", close_aria: "近くの一覧を閉じる", pane_aria: "近くのアーケード",
        search_area: "このエリアを検索", empty: "現在のフィルターに合う店舗がありません。ゲームやソースをオンにしてください。",
        nearest_you: "現在地から近い順", nearest_to: "{label} から近い順",
        showing: "フィルターに合う近い店舗 {n} 件を表示。座標のない店舗は含みません。",
        no_coords_note: "座標のない店舗は表示されません。", locate: "近くのアーケードを表示",
        your_location: "現在地", this_point: "この地点"
      },
      map: { aria: "アーケード地図" },
      empty: { map: "フィルターに合うアーケードがありません" },
      foot: { data_sources: "データソース", sources: "ソース", show: "データソース数を表示", hide: "データソース数を隠す" },
      lang: { button: "言語", menu: "言語を選択" },
      settings: {
        title: "設定", close: "設定を閉じる", sections: "設定セクション", gear: "設定",
        sec_sources: "ソース", sec_display: "表示", sec_location: "位置情報", sec_about: "について",
        sources_head: "データソース",
        sources_note: "ソースをオフにするとその店舗が隠れます。複数ソースにある店舗は、いずれかがオンなら表示されます。",
        display_head: "表示",
        marker_scaling: "筐体数でマーカーサイズ",
        marker_scaling_desc: "筐体が多い店舗ほど大きく描画。オフにすると全マーカー同サイズ（形はティアを表す）。",
        location_head: "位置情報",
        location_enabled: "位置情報機能を有効化",
        location_enabled_desc: "現在地ボタンと、近いアーケード一覧を表示します。",
        location_privacy: "位置情報はブラウザの外に出ません。",
        location_privacy_body: " 要求時のみ読み取り、距離ソートにのみ使用し、アップロード・保存・共有はしません。サーバーも解析もありません。",
        legend: "凡例",
        icon_cabinets: "アイコン：店舗の総筐体数",
        tier_unknown: "台数不明（中サイズで描画）",
        cluster_note: "12 店舗のクラスター。金縁は 20 台以上の店舗が含まれることを示します。",
        legend_note: "各ティアは形が違うため、大きさ比較なしで読めます。公式リストは多くがゲームのみで台数未掲載のため、不明は最小ではなく中ウェイトの専用アイコン（「未掲載」であり「1 台」ではない）。台数は BemaniCN と、実質データがある場合は ZIv。サイズは表示設定に従い、形は固定です。",
        icon_color: "アイコン色：店舗のゲーム",
        color_note: "複数ゲームの店舗は下の順で最初に選択されたゲームの色。上の凡例はサンプル色；地図上は店舗のゲーム色です。",
        badges: "店舗ポップアップのバッジ",
        cab_badge: "黄バッジはゲームではなく筐体：Lightning IIDX、Valkyrie / NEMSYS SOUND VOLTEX、DDR 金・Universal、GITADORA Arena、pop'n ピカピカ、太鼓の地域版など。筐体が譜面とモードを決めます。",
        dead_badge: "取り消し線バッジはオフライン筐体：maimai FiNALE と LCD 以前の DDR は遊べますがネットワーク終了済みで、スコア保存・解除・オンライン不可。",
        badge_note: "筐体データの出所と限界。公式は日本の機種のみ。国外はコミュニティの機種リスト。欠けたバッジは「未記録」であり「標準筐体」ではありません。SOUND VOLTEX の公式フィードは Valkyrie 有無で同じ店舗を返すため Valkyrie はコミュニティのみ；CHUNITHM 金/銀は実在しますがソースがなく推測しません。",
        about_map: "この地図について",
        stats: "{stores} 店舗、座標あり {plottable}。データ更新 {updated}。",
        link_source: "GitHub ソースコード", link_data: "データソース", link_license: "MIT ライセンス",
        osm_note: "地図データ (c) OpenStreetMap 貢献者、ODbL。店舗リストは各ソースに帰属し、ここは集約です。中国座標は GCJ-02 から変換した概算です。",
        shown: "現在のフィルターで地図上 {n} / {total} 店舗を表示。",
        src_extra: "その他のデータソース。",
        src_count_title: "このソースの店舗数（座標なしを含む）"
      },
      legend: {
        toggle: "凡例", icon_cabinets: "アイコン：店舗の筐体数", color_game: "色：ゲーム",
        full: "設定で完全な凡例", unknown_title: "台数不明、中サイズ"
      },
      src: {
        allnet_name: "ALL.Net", allnet_desc: "SEGA 公式店舗検索：maimai DX、CHUNITHM、O.N.G.E.K.I.",
        eagate_name: "e-amusement", eagate_desc: "KONAMI 公式店舗検索：IIDX、SOUND VOLTEX、DDR ほか Bemani。",
        wahlap_name: "WAHLAP", wahlap_desc: "中国本土の SEGA 公式ディストリビューター。住所のみ、座標なし。",
        bemanicn_name: "BemaniCN", bemanicn_desc: "中国本土の Bemani 筐体コミュニティ地図。",
        ziv_name: "Zenius-I-Vanisher", ziv_desc: "世界規模のコミュニティ・アーケードDB。",
        round1usa_name: "Round1 USA", round1usa_desc: "米国 Round1 公式店舗リスト。",
        community_name: "Community", community_desc: "このリポジトリで手作業のエントリ。"
      },
      place: {
        directions: "ルート", nearby: "近く", share: "共有", filters: "フィルター",
        close: "店舗詳細を閉じる", details: "店舗詳細",
        address_copied: "住所をコピーしました", link_copied: "リンクをコピーしました", copy_failed: "コピー失敗",
        tap_to_copy: "タップしてコピー",
        listed_by: "掲載元",
        no_map_position: "この店舗の地図位置がありません",
        no_map_position_cap: "住所のみ公開されています。「ルート」で検索してください。",
        community_from: "{src} のコミュニティデータ（古い可能性あり{date}）",
        community_listings: "コミュニティ掲載",
        rechecked_community: "{host} で再確認済み（コミュニティデータのまま）",
        checked_operator: "{host} と照合済み",
        checked_operator_generic: "運営の公式ページと照合済み",
        price_common: "ここに掲載の {n} 台のうち最頻出の料金。",
        per_machine: "掲載どおり1台あたり。",
        machine_list_no_counts: "機種リストはあるが台数なし",
        machine_list_no_counts_cap: "コミュニティ一覧は機種名だけで台数を書いていないため、下限であり実数ではありません。",
        cab_counts_unavailable: "台数情報なし",
        cab_counts_unavailable_cap: "この店舗の出典は台数を公開していません。",
        approx_address: "位置は住所から",
        approx_address_cap: "出典に座標がなく、印刷住所からジオコーディングした位置です。",
        approx_street: "位置は住所から（道路レベル）",
        approx_street_cap: "建物ではなく道路に付けているため、数軒ずれることがあります。",
        approx_district: "位置はおよそそ（区レベル）",
        approx_district_cap: "出典に座標がなく、住所の区の中心です（店舗そのものではありません）。",
        approx_city: "位置はおよそそ（市レベル）",
        approx_city_cap: "出典に座標がなく区名もないため、市の中心です。",
        back_to: "{label}に戻る",
        search_gmaps: "Google マップで検索",
      },
      nb: {
        err_denied: "位置情報の許可が拒否されました。ブラウザ設定で許可してから再試行してください。",
        err_unavailable: "現在地を取得できません。再試行するか、都市名で検索してください。",
        err_timeout: "位置情報の取得がタイムアウトしました。再試行してください。",
        err_generic: "現在地を取得できませんでした。",
        err_empty: "位置情報が空でした。しばらくして再試行してください。",
        err_off: "設定で位置情報機能がオフです。",
        err_https: "位置情報にはセキュア（https）接続が必要です。",
        err_unsupported: "このブラウザは位置情報を報告できません。"
      },
      cabs: {
        sdvx_vm: "Valkyrieモデル",
        iidx_lm: "Lightningモデル",
        ddr_gold: "ゴールド筐体（20周年）",
        gitadora_arena: "Arenaモデル",
        popn_pikapika: "ピカピカモデル",
        maimai_classic: "maimai FiNALE / 旧筐体",
        sdvx_nemsys: "NEMSYS（標準）",
        ddr_universal: "Universal Model（欧米）",
        ddr_legacy: "旧型CRT筐体",
        other_game: "その他",
      },
      ui: {
        shown: "{n} 件表示",
        stores_total: "全{n} 店",
        per_credit: "/クレジット",
        show_more: "もっと見る",
        show_less: "折りたたむ",
        search_wide: "ゲーム・店舗・場所を検索...",
        search_narrow: "検索...",
        cab_model_unpublished: "筐体モデル未公開",
        cab_model_unpublished_cap: "どの筐体かを明記した情報がありません。公式の筐体データは日本のみ。コミュニティ掲載は記録された場合だけです。「標準」ではなく「不明」です。",
        offline_cab: "オフライン筐体",
        offline_cabs: "オフライン筐体",
        offline_cap: "この筐体のネットワークは終了しています。遊べますがスコア保存・オンライン・アンロックはできません。",
        price_median: "{game}、{country}で引用{n}件の中央値。この店の実際料金ではありません。",
        price_sparse: "{country}で{n}件の情報のみ{for_game}。目安として取ってください。",
        for_game: "（{game}）",
        typical_country: "{country}の典型価格 - この店の実際料金ではありません",
        permanently_closed: "閉店済み。",
        source: "出典",
        photo_by: "写真: {credit}",
        unknown_author: "不明",
        listed: "掲載",
        size_1: "1〜2 台",
        size_2: "3〜9 台",
        size_3: "10〜19 台",
        size_4: "20〜49 台",
        size_5: "50 台以上（巨大店）",
        size_U: "台数不明",
      }
    },

    ko: {
      app: { title: "아케이드 맵", updated: "업데이트 {date}", data_failed: "데이터 로드 실패" },
      drawer: { toggle: "필터 전환", toggle_title: "필터 패널 전환" },
      meta: { updated_title: "데이터 최종 업데이트", count_title: "표시 마커 / 지도상 매장" },
      search: { placeholder: "이름 또는 주소 검색...", aria: "이름 또는 주소로 아케이드 검색" },
      repo: { title: "GitHub 저장소", aria: "GitHub 저장소" },
      tab: { filters: "필터", china: "좌표 없음 목록" },
      pane: { games: "게임", cab_variants: "기체 변형",
        arcade_size: "아케이드 규모" },
      btn: { all: "전체", none: "없음" },
      hint: {
        cab_variant: "변형을 선택하면 해당 기체가 있는 매장 마커만 표시됩니다.",
        arcade_size: "기체 수 구간은 지도 마커 모양과 일치합니다. 미상은 신뢰할 수 있는 공개 수가 없음을 뜻합니다.",
        china1: "지도 좌표가 없는 매장(주로 중국).",
        china2: "공식 WAHLAP 목록과 BemaniCN 커뮤니티 지도의 주소만 있습니다. 지도 앱에서 주소를 검색하세요. 중국 웹 지도는 GCJ-02를 사용하며, 지도에 그려진 중국 지점은 WGS-84로 변환되어 대략적입니다."
      },
      nearby: {
        title: "근처 아케이드", close: "닫기", close_aria: "근처 목록 닫기", pane_aria: "근처 아케이드",
        search_area: "이 영역 검색", empty: "현재 필터에 맞는 매장이 없습니다. 게임이나 소스를 다시 켜세요.",
        nearest_you: "내 위치에서 가까운 순", nearest_to: "{label}에서 가까운 순",
        showing: "필터에 맞는 가장 가까운 매장 {n}곳. 좌표 없는 매장은 표시되지 않습니다.",
        no_coords_note: "좌표 없는 매장은 표시되지 않습니다.", locate: "내 근처 아케이드 보기",
        your_location: "내 위치", this_point: "이 지점"
      },
      map: { aria: "아케이드 지도" },
      empty: { map: "필터에 맞는 아케이드가 없습니다" },
      foot: { data_sources: "데이터 출처", sources: "출처", show: "데이터 출처 수 표시", hide: "데이터 출처 수 숨기기" },
      lang: { button: "언어", menu: "언어 선택" },
      settings: {
        title: "설정", close: "설정 닫기", sections: "설정 섹션", gear: "설정",
        sec_sources: "소스", sec_display: "표시", sec_location: "위치", sec_about: "정보",
        sources_head: "데이터 소스",
        sources_note: "소스를 끄면 해당 매장이 숨겨집니다. 여러 소스에 있는 매장은 하나라도 켜져 있으면 표시됩니다.",
        display_head: "표시",
        marker_scaling: "기체 수로 마커 크기",
        marker_scaling_desc: "기체가 많은 매장일수록 크게 그립니다. 끄면 모든 마커가 같은 크기(모양은 티어).",
        location_head: "위치",
        location_enabled: "위치 기능 사용",
        location_enabled_desc: "위치 버튼과 가장 가까운 아케이드 목록을 표시합니다.",
        location_privacy: "위치는 브라우저 밖으로 나가지 않습니다.",
        location_privacy_body: " 요청 시에만 읽고 거리 정렬에만 쓰이며 업로드·저장·공유되지 않습니다. 서버와 분석이 없습니다.",
        legend: "범례",
        icon_cabinets: "아이콘: 매장 총 기체 수",
        tier_unknown: "대수 미상(중간 크기)",
        cluster_note: "12개 매장 클러스터. 금색 테두리는 20대 이상 매장이 포함됨을 뜻합니다.",
        legend_note: "각 티어는 모양이 달라 크기 비교 없이 읽을 수 있습니다. 공식 목록은 게임만 있고 대수가 없는 경우가 많아, 미상은 최소가 아닌 중간 전용 아이콘입니다. 대수는 BemaniCN과 실질 데이터가 있을 때 ZIv. 크기는 표시 설정, 모양은 고정.",
        icon_color: "아이콘 색: 매장 게임",
        color_note: "여러 게임 매장은 아래 순서로 처음 선택된 게임 색. 위 범례는 샘플 색; 지도에서는 매장 게임 색.",
        badges: "매장 팝업 배지",
        cab_badge: "노란 배지는 게임이 아니라 기체: Lightning IIDX, Valkyrie/NEMSYS SOUND VOLTEX, DDR 골드·Universal, GITADORA Arena, pop'n ピカピカ, 태고 지역판 등.",
        dead_badge: "취소선 배지는 오프라인 기체: maimai FiNALE와 LCD 이전 DDR은 플레이 가능하나 네트워크 종료로 점수 저장·해금·온라인이 불가합니다.",
        badge_note: "기체 데이터 출처와 한계. 공식은 일본 기종만 공개. 해외는 커뮤니티 목록. 없는 배지는 ‘미기록’이지 ‘표준 기체’가 아닙니다.",
        about_map: "이 지도 정보",
        stats: "매장 {stores}곳, 좌표 있음 {plottable}. 데이터 업데이트 {updated}.",
        link_source: "GitHub 소스 코드", link_data: "데이터 출처", link_license: "MIT 라이선스",
        osm_note: "지도 데이터 (c) OpenStreetMap 기여자, ODbL. 매장 목록은 각 출처 소유이며 여기선 집계입니다. 중국 좌표는 GCJ-02 변환 근사치입니다.",
        shown: "현재 필터로 지도상 {n} / {total} 매장 표시.",
        src_extra: "추가 데이터 소스.",
        src_count_title: "이 소스의 매장 수(좌표 없음 포함)"
      },
      legend: {
        toggle: "범례", icon_cabinets: "아이콘: 매장 기체 수", color_game: "색: 게임",
        full: "설정에서 전체 범례", unknown_title: "대수 미상, 중간 크기"
      },
      src: {
        allnet_name: "ALL.Net", allnet_desc: "SEGA 공식 매장 검색: maimai DX, CHUNITHM, O.N.G.E.K.I.",
        eagate_name: "e-amusement", eagate_desc: "KONAMI 공식 매장 검색: IIDX, SOUND VOLTEX, DDR 및 기타 Bemani.",
        wahlap_name: "WAHLAP", wahlap_desc: "중국 본토 SEGA 공식 유통. 주소만, 좌표 없음.",
        bemanicn_name: "BemaniCN", bemanicn_desc: "중국 본토 Bemani 기체 커뮤니티 지도.",
        ziv_name: "Zenius-I-Vanisher", ziv_desc: "전 세계 커뮤니티 아케이드 DB.",
        round1usa_name: "Round1 USA", round1usa_desc: "미국 Round1 공식 매장 목록.",
        community_name: "Community", community_desc: "이 저장소에서 수동 정리한 항목."
      },
      place: {
        directions: "길찾기", nearby: "근처", share: "공유", filters: "필터",
        close: "매장 상세 닫기", details: "매장 상세",
        address_copied: "주소 복사됨", link_copied: "링크 복사됨", copy_failed: "복사 실패",
        tap_to_copy: "탭하여 복사",
        listed_by: "수록 출처",
        no_map_position: "이 매장의 지도 위치가 없습니다",
        no_map_position_cap: "주소만 공개되어 있습니다. 「길찾기」로 검색하세요.",
        community_from: "{src} 커뮤니티 데이터(오래되었을 수 있음{date})",
        community_listings: "커뮤니티 목록",
        rechecked_community: "{host}에서 재확인함(여전히 커뮤니티 데이터)",
        checked_operator: "{host}와 대조 확인함",
        checked_operator_generic: "운영사 공식 페이지와 대조 확인함",
        price_common: "여기 나열된 {n}대 중 가장 흔한 요금.",
        per_machine: "목록 기준 1대당.",
        machine_list_no_counts: "기체 목록은 있으나 대수 없음",
        machine_list_no_counts_cap: "커뮤니티 목록은 기체 이름만 있고 대수 없이 하한일 뿐입니다.",
        cab_counts_unavailable: "대수 정보 없음",
        cab_counts_unavailable_cap: "이 매장 출처는 대수를 공개하지 않습니다.",
        approx_address: "위치는 주소에서",
        approx_address_cap: "출처에 좌표가 없어 인쇄 주소를 지오코딩한 위치입니다.",
        approx_street: "위치는 주소에서(도로 수준)",
        approx_street_cap: "건물이 아니라 도로에 맞춰 몇 문짝 어귳날 수 있습니다.",
        approx_district: "대략적 위치(구 수준)",
        approx_district_cap: "좌표 없이 주소의 구 중심입니다(매장 자체 아님).",
        approx_city: "대략적 위치(시 수준)",
        approx_city_cap: "좌표와 구 이름이 없어 시 중심입니다.",
        back_to: "{label}(으)로 돌아가기",
        search_gmaps: "Google 지도에서 검색",
      },
      nb: {
        err_denied: "위치 권한이 거부되었습니다. 브라우저 설정에서 허용한 뒤 다시 시도하세요.",
        err_unavailable: "지금 위치를 사용할 수 없습니다. 다시 시도하거나 도시로 검색하세요.",
        err_timeout: "위치 가져오기가 너무 오래 걸렸습니다. 다시 시도하세요.",
        err_generic: "위치를 가져올 수 없습니다.",
        err_empty: "위치가 비어 있습니다. 잠시 후 다시 시도하세요.",
        err_off: "설정에서 위치 기능이 꺼져 있습니다.",
        err_https: "위치에는 보안(https) 연결이 필요합니다.",
        err_unsupported: "이 브라우저는 위치를 보고할 수 없습니다."
      },
      cabs: {
        sdvx_vm: "Valkyrie 모델",
        iidx_lm: "Lightning 모델",
        ddr_gold: "골드 캐비넷(20주년)",
        gitadora_arena: "Arena 모델",
        popn_pikapika: "피카피카 모델",
        maimai_classic: "maimai FiNALE / 구기체",
        sdvx_nemsys: "NEMSYS(표준)",
        ddr_universal: "Universal Model(유/미)",
        ddr_legacy: "레거시 CRT 캐비넷",
        other_game: "기타",
      },
      ui: {
        shown: "{n}개 표시",
        stores_total: "전체 {n}개 매장",
        per_credit: "/크레딧",
        show_more: "더 보기",
        show_less: "접기",
        search_wide: "게임·아케이드·장소 검색...",
        search_narrow: "검색...",
        cab_model_unpublished: "기체 모델 미공개",
        cab_model_unpublished_cap: "이 매장이 어떤 기체인지 적힌 목록이 없습니다. 공식 기체 데이터는 일본만. 커뮤니티는 기록된 경우만. “표준”이 아니라 “미상”입니다.",
        offline_cab: "오프라인 기체",
        offline_cabs: "오프라인 기체",
        offline_cap: "이 기체 네트워크는 종료되었습니다. 플레이는 가능하지만 점수 저장·온라인·언락은 불가능합니다.",
        price_median: "{game}, {country} {n}개 가격의 중위값. 이 매장 실제 가격 아님.",
        price_sparse: "{country} {n}개 정보만{for_game}. 참고로만.",
        for_game: " ({game})",
        typical_country: "{country} 표준가 - 이 매장 가격 아님",
        permanently_closed: "영구 폐업.",
        source: "출처",
        photo_by: "사진: {credit}",
        unknown_author: "미상",
        listed: "등록",
        size_1: "1–2대",
        size_2: "3–9대",
        size_3: "10–19대",
        size_4: "20–49대",
        size_5: "50대 이상(메가)",
        size_U: "대수 미상",
      }
    },

    id: {
      app: { title: "Peta Arkade", updated: "diperbarui {date}", data_failed: "gagal memuat data" },
      drawer: { toggle: "Buka/tutup filter", toggle_title: "Buka/tutup panel filter" },
      meta: { updated_title: "Data terakhir diperbarui", count_title: "Penanda tampil / toko yang bisa dipetakan" },
      search: { placeholder: "Cari nama atau alamat...", aria: "Cari arkade berdasarkan nama atau alamat" },
      repo: { title: "Repositori GitHub", aria: "Repositori GitHub" },
      tab: { filters: "Filter", china: "Tanpa koordinat" },
      pane: { games: "Game", cab_variants: "Varian kabinet",
        arcade_size: "Ukuran arkade" },
      btn: { all: "semua", none: "tidak ada" },
      hint: {
        cab_variant: "Memilih varian membatasi penanda game itu ke toko yang punya kabinet tersebut.",
        arcade_size: "Pita jumlah kabinet cocok dengan bentuk penanda peta. Tidak diketahui berarti tidak ada hitungan tepercaya yang dipublikasikan.",
        china1: "Toko tanpa koordinat peta (sebagian besar China).",
        china2: "Dari daftar resmi WAHLAP dan peta komunitas BemaniCN (alamat saja). Cari alamat di aplikasi peta. Peta web China memakai GCJ-02; titik China di peta dikonversi ke WGS-84 (perkiraan)."
      },
      nearby: {
        title: "Arkade terdekat", close: "tutup", close_aria: "Tutup daftar terdekat", pane_aria: "Arkade terdekat",
        search_area: "Cari area ini", empty: "Tidak ada toko yang cocok dengan filter. Nyalakan lagi game atau sumber.",
        nearest_you: "Terdekat dari lokasi Anda", nearest_to: "Terdekat dari {label}",
        showing: "Menampilkan {n} toko terdekat yang cocok. Tanpa koordinat tidak ditampilkan.",
        no_coords_note: "Toko tanpa koordinat tidak ditampilkan.", locate: "Tampilkan arkade di dekat saya",
        your_location: "lokasi Anda", this_point: "titik ini"
      },
      map: { aria: "Peta arkade" },
      empty: { map: "Tidak ada arkade yang cocok dengan filter" },
      foot: { data_sources: "sumber data", sources: "sumber", show: "Tampilkan jumlah sumber data", hide: "Sembunyikan jumlah sumber data" },
      lang: { button: "Bahasa", menu: "Pilih bahasa" },
      settings: {
        title: "Pengaturan", close: "Tutup pengaturan", sections: "Bagian pengaturan", gear: "Pengaturan",
        sec_sources: "Sumber", sec_display: "Tampilan", sec_location: "Lokasi", sec_about: "Tentang",
        sources_head: "Sumber data",
        sources_note: "Matikan sumber untuk menyembunyikan tokonya. Toko di beberapa sumber tetap tampil selama salah satunya aktif.",
        display_head: "Tampilan",
        marker_scaling: "Ukuran penanda menurut jumlah kabinet",
        marker_scaling_desc: "Toko lebih ramai digambar lebih besar. Matikan agar semua penanda sama ukuran (bentuk tetap menunjukkan tingkat).",
        location_head: "Lokasi",
        location_enabled: "Aktifkan fitur lokasi",
        location_enabled_desc: "Tampilkan tombol lokasi dan daftar arkade terdekat.",
        location_privacy: "Lokasi Anda tidak pernah meninggalkan browser.",
        location_privacy_body: " Hanya dibaca setelah Anda meminta, dipakai untuk mengurutkan jarak di halaman ini, dan tidak diunggah, disimpan, atau dibagikan. Situs ini tanpa server dan analitik.",
        legend: "Legenda",
        icon_cabinets: "Ikon: total kabinet di toko",
        tier_unknown: "Jumlah tidak diketahui (ukuran sedang)",
        cluster_note: "Klaster 12 toko. Bingkai emas berarti ada toko 20+ kabinet di dalamnya.",
        legend_note: "Setiap tingkat bentuknya beda. Kebanyakan daftar resmi memuat game tapi bukan jumlah kabinet, jadi jumlah tak diketahui punya ikon menengah sendiri (\"tidak dipublikasikan\", bukan \"satu kabinet\"). Jumlah dari BemaniCN dan ZIv bila ada data. Ukuran mengikuti tampilan; bentuk tetap.",
        icon_color: "Warna ikon: game di toko",
        color_note: "Toko dengan beberapa game memakai warna game terpilih pertama dalam urutan di bawah. Legenda di atas warna sampel; di peta mengikuti warna game toko.",
        badges: "Lencana di popup toko",
        cab_badge: "Lencana kuning menamai KABINET, bukan game: Lightning IIDX, Valkyrie/NEMSYS SOUND VOLTEX, DDR gold & Universal, GITADORA Arena, pop'n Pikapika, dan build regional Taiko.",
        dead_badge: "Lencana dicoret adalah kabinet OFFLINE: maimai FiNALE dan DDR pra-LCD masih jalan, tapi jaringannya mati - tanpa skor, unlock, atau online.",
        badge_note: "Asal data kabinet dan batasannya. Daftar operator resmi hanya Jepang; di luar itu dari daftar komunitas. Lencana hilang = model belum dicatat, bukan kabinet standar.",
        about_map: "Tentang peta ini",
        stats: "{stores} toko, {plottable} berkoordinat. Data diperbarui {updated}.",
        link_source: "Kode sumber di GitHub", link_data: "Sumber data", link_license: "Lisensi MIT",
        osm_note: "Data peta (c) kontributor OpenStreetMap, ODbL. Daftar toko milik sumber masing-masing. Koordinat China dikonversi dari GCJ-02 (perkiraan).",
        shown: "{n} dari {total} toko terpetakan ditampilkan dengan filter saat ini.",
        src_extra: "Sumber data tambahan.",
        src_count_title: "toko dari sumber ini, termasuk tanpa koordinat"
      },
      legend: {
        toggle: "Legenda", icon_cabinets: "Ikon: kabinet di toko", color_game: "Warna: game",
        full: "Legenda lengkap di Pengaturan", unknown_title: "jumlah tak diketahui, ukuran sedang"
      },
      src: {
        allnet_name: "ALL.Net", allnet_desc: "Pencari toko resmi SEGA: maimai DX, CHUNITHM, O.N.G.E.K.I.",
        eagate_name: "e-amusement", eagate_desc: "Pencari toko resmi KONAMI: IIDX, SOUND VOLTEX, DDR, dan Bemani lain.",
        wahlap_name: "WAHLAP", wahlap_desc: "Distributor resmi SEGA Tiongkok daratan. Alamat saja, tanpa koordinat.",
        bemanicn_name: "BemaniCN", bemanicn_desc: "Peta komunitas kabinet Bemani di Tiongkok daratan.",
        ziv_name: "Zenius-I-Vanisher", ziv_desc: "Basis data arkade komunitas cakupan dunia.",
        round1usa_name: "Round1 USA", round1usa_desc: "Daftar venue resmi Round1 Amerika Serikat.",
        community_name: "Community", community_desc: "Entri yang dikurasi manual di repositori ini."
      },
      place: {
        directions: "Petunjuk arah", nearby: "Terdekat", share: "Bagikan", filters: "Filter",
        close: "Tutup detail tempat", details: "Detail tempat",
        address_copied: "Alamat disalin", link_copied: "Tautan disalin", copy_failed: "Gagal menyalin",
        tap_to_copy: "Ketuk untuk salin",
        listed_by: "Dicantumkan oleh",
        no_map_position: "Toko ini tidak punya posisi peta",
        no_map_position_cap: "Hanya alamat yang dipublikasikan. Gunakan Petunjuk arah untuk mencari.",
        community_from: "data komunitas dari {src}, mungkin usang{date}",
        community_listings: "daftar komunitas",
        rechecked_community: "dicek ulang di {host}, masih data komunitas",
        checked_operator: "dicek terhadap {host}",
        checked_operator_generic: "dicek terhadap daftar resmi operator",
        price_common: "Harga paling umum di antara {n} mesin yang tercantum di sini.",
        per_machine: "Per mesin, sesuai daftar.",
        machine_list_no_counts: "Ada daftar mesin, tanpa jumlah kabinet",
        machine_list_no_counts_cap: "Daftar komunitas menamai mesin di bawah tanpa bilang berapa unit tiap jenis, jadi ini batas bawah, bukan hitungan pasti.",
        cab_counts_unavailable: "Jumlah kabinet tidak tersedia",
        cab_counts_unavailable_cap: "Sumber toko ini tidak memublikasikan berapa banyak mesin.",
        approx_address: "Posisi dari alamat",
        approx_address_cap: "Sumber tanpa koordinat; pin di-geocode dari alamat tercetak.",
        approx_street: "Posisi dari alamat (level jalan)",
        approx_street_cap: "Ter-geocode ke jalan, bukan bangunan; bisa meleset satu-dua pintu.",
        approx_district: "Posisi perkiraan (level distrik)",
        approx_district_cap: "Tanpa koordinat; pin di pusat distrik pada alamat, bukan toko.",
        approx_city: "Posisi perkiraan (level kota)",
        approx_city_cap: "Tanpa koordinat dan tanpa nama distrik; pin di pusat kota.",
        back_to: "Kembali ke {label}",
        search_gmaps: "Cari di Google Maps",
      },
      nb: {
        err_denied: "Izin lokasi ditolak. Izinkan di pengaturan browser, lalu coba lagi.",
        err_unavailable: "Lokasi tidak tersedia. Coba lagi, atau cari kota.",
        err_timeout: "Mendapatkan lokasi terlalu lama. Coba lagi.",
        err_generic: "Tidak bisa mendapatkan lokasi Anda.",
        err_empty: "Lokasi kosong. Coba lagi sebentar.",
        err_off: "Lokasi dimatikan di pengaturan.",
        err_https: "Lokasi membutuhkan koneksi aman (https).",
        err_unsupported: "Browser ini tidak bisa melaporkan lokasi."
      },
      cabs: {
        sdvx_vm: "Model Valkyrie",
        iidx_lm: "Model Lightning",
        ddr_gold: "Kabinet emas (ultah ke-20)",
        gitadora_arena: "Model Arena",
        popn_pikapika: "Model Pikapika",
        maimai_classic: "maimai FiNALE / pra-DX",
        sdvx_nemsys: "NEMSYS (standar)",
        ddr_universal: "Universal Model (EU/NA)",
        ddr_legacy: "Kabinet CRT lama",
        other_game: "Lainnya",
      },
      ui: {
        shown: "{n} ditampilkan",
        stores_total: "{n} toko total",
        per_credit: "per kredit",
        show_more: "Tampilkan lebih",
        show_less: "Tampilkan kurang",
        search_wide: "Cari game, arkade, tempat...",
        search_narrow: "Cari...",
        cab_model_unpublished: "Cabinet model not published",
        cab_model_unpublished_cap: "No listing says which cabinet this store runs. Official cab data covers Japan only, and community listings record the model just when someone noted it - so this is \"unknown\", not \"standard\".",
        offline_cab: "offline cabinet",
        offline_cabs: "offline cabinets",
        offline_cap: "This cabinet's network has shut down. It can still be played, but nothing is saved: no score history, no online play, no unlocks.",
        price_median: "{game}, median of {n} quoted prices in {country}. Not this store's own price.",
        price_sparse: "Based on only {n} listing(s) in {country}{for_game}, so treat it as a rough guide.",
        for_game: " for {game}",
        typical_country: "Typical for {country} - not this store's own price",
        permanently_closed: "Tutup permanen.",
        source: "sumber",
        photo_by: "photo: {credit}",
        unknown_author: "unknown",
        size_1: "1 to 2 cabinets",
        size_2: "3 to 9 cabinets",
        size_3: "10 to 19 cabinets",
        size_4: "20 to 49 cabinets",
        size_5: "50 or more cabinets (mega arcade)",
        size_U: "Count unknown",
      }
    },

    ms: {
      app: { title: "Peta Arked", updated: "dikemas kini {date}", data_failed: "gagal memuatkan data" },
      drawer: { toggle: "Togol penapis", toggle_title: "Togol panel penapis" },
      meta: { updated_title: "Data dikemas kini terakhir", count_title: "Penanda dipaparkan / kedai boleh dipetakan" },
      search: { placeholder: "Cari nama atau alamat...", aria: "Cari arked mengikut nama atau alamat" },
      repo: { title: "Repositori GitHub", aria: "Repositori GitHub" },
      tab: { filters: "Penapis", china: "Tanpa koordinat" },
      pane: { games: "Permainan", cab_variants: "Varian kabinet",
        arcade_size: "Saiz arked" },
      btn: { all: "semua", none: "tiada" },
      hint: {
        cab_variant: "Memilih varian mengehadkan penanda permainan itu kepada kedai yang mempunyai kabinet tersebut.",
        arcade_size: "Jalur bilangan kabinet sepadan dengan bentuk penanda peta. Tidak diketahui bermaksud tiada bilangan dipercayai yang diterbitkan.",
        china1: "Kedai tanpa koordinat peta (kebanyakannya China).",
        china2: "Dari senarai rasmi WAHLAP dan peta komuniti BemaniCN (alamat sahaja). Cari alamat dalam aplikasi peta. Peta web China menggunakan GCJ-02; titik China pada peta ditukar kepada WGS-84 (anggaran)."
      },
      nearby: {
        title: "Arked berdekatan", close: "tutup", close_aria: "Tutup senarai berdekatan", pane_aria: "Arked berdekatan",
        search_area: "Cari kawasan ini", empty: "Tiada kedai sepadan penapis. Hidupkan semula permainan atau sumber.",
        nearest_you: "Terdekat dari lokasi anda", nearest_to: "Terdekat dari {label}",
        showing: "Memaparkan {n} kedai terdekat yang sepadan. Tanpa koordinat tidak dipaparkan.",
        no_coords_note: "Kedai tanpa koordinat tidak dipaparkan.", locate: "Tunjukkan arked berdekatan saya",
        your_location: "lokasi anda", this_point: "titik ini"
      },
      map: { aria: "Peta arked" },
      empty: { map: "Tiada arked sepadan penapis anda" },
      foot: { data_sources: "sumber data", sources: "sumber", show: "Tunjuk bilangan sumber data", hide: "Sembunyi bilangan sumber data" },
      lang: { button: "Bahasa", menu: "Pilih bahasa" },
      settings: {
        title: "Tetapan", close: "Tutup tetapan", sections: "Bahagian tetapan", gear: "Tetapan",
        sec_sources: "Sumber", sec_display: "Paparan", sec_location: "Lokasi", sec_about: "Perihal",
        sources_head: "Sumber data",
        sources_note: "Matikan sumber untuk menyembunyikan kedainya. Kedai dalam beberapa sumber kekal dipaparkan selagi salah satu aktif.",
        display_head: "Paparan",
        marker_scaling: "Saiz penanda mengikut bilangan kabinet",
        marker_scaling_desc: "Kedai lebih sibuk dilukis lebih besar. Matikan supaya semua penanda saiz sama (bentuk masih menunjukkan peringkat).",
        location_head: "Lokasi",
        location_enabled: "Dayakan ciri lokasi",
        location_enabled_desc: "Tunjuk butang lokasi dan senarai arked terdekat.",
        location_privacy: "Lokasi anda tidak pernah meninggalkan pelayar.",
        location_privacy_body: " Hanya dibaca selepas anda minta, digunakan untuk menyusun jarak di halaman ini, dan tidak dimuat naik, disimpan atau dikongsi. Laman ini tiada pelayan dan analitik.",
        legend: "Legenda",
        icon_cabinets: "Ikon: jumlah kabinet di kedai",
        tier_unknown: "Bilangan tidak diketahui (saiz sederhana)",
        cluster_note: "Kluster 12 kedai. Bingkai emas bermaksud sekurang-kurangnya satu kedai 20+ kabinet di dalamnya.",
        legend_note: "Setiap peringkat bentuk berbeza. Kebanyakan senarai rasmi ada permainan tetapi bukan bilangan kabinet, jadi bilangan tidak diketahui mendapat ikon sederhana tersendiri. Bilangan dari BemaniCN dan ZIv bila ada. Saiz ikut tetapan paparan; bentuk tetap.",
        icon_color: "Warna ikon: permainan di kedai",
        color_note: "Kedai berbilang permainan mengambil warna permainan terpilih pertama dalam susunan di bawah. Legenda di atas warna sampel; di peta mengikut warna permainan kedai.",
        badges: "Lencana dalam pop timbul kedai",
        cab_badge: "Lencana kuning menamakan KABINET, bukan permainan: Lightning IIDX, Valkyrie/NEMSYS SOUND VOLTEX, DDR gold & Universal, GITADORA Arena, pop'n Pikapika, dan binaan wilayah Taiko.",
        dead_badge: "Lencana dicoret ialah kabinet LUAR TALIAN: maimai FiNALE dan DDR pra-LCD masih boleh dimainkan, tetapi rangkaian ditutup - tiada skor, buka kunci, atau dalam talian.",
        badge_note: "Asal data kabinet dan hadnya. Senarai operator rasmi hanya Jepun; di luar itu dari senarai komuniti. Lencana hilang = model belum direkod, bukan kabinet standard.",
        about_map: "Perihal peta ini",
        stats: "{stores} kedai, {plottable} berkoordinat. Data dikemas kini {updated}.",
        link_source: "Kod sumber di GitHub", link_data: "Sumber data", link_license: "Lesen MIT",
        osm_note: "Data peta (c) penyumbang OpenStreetMap, ODbL. Senarai kedai milik sumber masing-masing. Koordinat China ditukar dari GCJ-02 (anggaran).",
        shown: "{n} daripada {total} kedai boleh dipetakan dipaparkan dengan penapis semasa.",
        src_extra: "Sumber data tambahan.",
        src_count_title: "kedai dari sumber ini, termasuk tanpa koordinat"
      },
      legend: {
        toggle: "Legenda", icon_cabinets: "Ikon: kabinet di kedai", color_game: "Warna: permainan",
        full: "Legenda penuh dalam Tetapan", unknown_title: "bilangan tidak diketahui, saiz sederhana"
      },
      src: {
        allnet_name: "ALL.Net", allnet_desc: "Pencari kedai rasmi SEGA: maimai DX, CHUNITHM, O.N.G.E.K.I.",
        eagate_name: "e-amusement", eagate_desc: "Pencari kedai rasmi KONAMI: IIDX, SOUND VOLTEX, DDR dan Bemani lain.",
        wahlap_name: "WAHLAP", wahlap_desc: "Pengedar rasmi SEGA China daratan. Alamat sahaja, tiada koordinat.",
        bemanicn_name: "BemaniCN", bemanicn_desc: "Peta komuniti kabinet Bemani di China daratan.",
        ziv_name: "Zenius-I-Vanisher", ziv_desc: "Pangkalan data arked komuniti liputan sedunia.",
        round1usa_name: "Round1 USA", round1usa_desc: "Senarai venue rasmi Round1 Amerika Syarikat.",
        community_name: "Community", community_desc: "Entri dikurasi secara manual dalam repositori ini."
      },
      place: {
        directions: "Arah", nearby: "Berdekatan", share: "Kongsi", filters: "Penapis",
        close: "Tutup butiran tempat", details: "Butiran tempat",
        address_copied: "Alamat disalin", link_copied: "Pautan disalin", copy_failed: "Gagal salin",
        tap_to_copy: "Ketik untuk salin",
        listed_by: "Disenaraikan oleh",
        no_map_position: "Kedai ini tiada kedudukan peta",
        no_map_position_cap: "Hanya alamat diterbitkan. Gunakan Arah untuk mencari.",
        community_from: "data komuniti daripada {src}, mungkin lapuk{date}",
        community_listings: "senarai komuniti",
        rechecked_community: "disemak semula di {host}, masih data komuniti",
        checked_operator: "disemak berbanding {host}",
        checked_operator_generic: "disemak berbanding senarai rasmi pengendali",
        price_common: "Harga paling biasa merentasi {n} mesin tersenarai di sini.",
        per_machine: "Setiap mesin, seperti disenaraikan.",
        machine_list_no_counts: "Ada senarai mesin, tiada bilangan kabinet",
        machine_list_no_counts_cap: "Senarai komuniti menamakan mesin di bawah tanpa bilangan unit, jadi ini had bawah, bukan kiraan penuh.",
        cab_counts_unavailable: "Bilangan kabinet tidak tersedia",
        cab_counts_unavailable_cap: "Sumber kedai ini tidak menerbitkan berapa banyak mesin.",
        approx_address: "Kedudukan daripada alamat",
        approx_address_cap: "Sumber tiada koordinat; pin digeokod daripada alamat bercetak.",
        approx_street: "Kedudukan daripada alamat (level jalan)",
        approx_street_cap: "Digeokod ke jalan, bukan bangunan; mungkin silap satu-dua pintu.",
        approx_district: "Kedudukan anggaran (level daerah)",
        approx_district_cap: "Tiada koordinat; pin di pusat daerah pada alamat, bukan kedai.",
        approx_city: "Kedudukan anggaran (level bandar)",
        approx_city_cap: "Tiada koordinat dan tiada nama daerah; pin di pusat bandar.",
        back_to: "Kembali ke {label}",
        search_gmaps: "Cari di Google Maps",
      },
      nb: {
        err_denied: "Kebenaran lokasi ditolak. Benarkan dalam tetapan pelayar, kemudian cuba lagi.",
        err_unavailable: "Lokasi tidak tersedia. Cuba lagi, atau cari bandar.",
        err_timeout: "Mendapat lokasi terlalu lama. Cuba lagi.",
        err_generic: "Tidak dapat mendapatkan lokasi anda.",
        err_empty: "Lokasi kosong. Cuba lagi sebentar.",
        err_off: "Lokasi dimatikan dalam tetapan.",
        err_https: "Lokasi memerlukan sambungan selamat (https).",
        err_unsupported: "Pelayar ini tidak dapat melaporkan lokasi."
      },
      cabs: {
        sdvx_vm: "Model Valkyrie",
        iidx_lm: "Model Lightning",
        ddr_gold: "Kabinet emas (ulang tahun ke-20)",
        gitadora_arena: "Model Arena",
        popn_pikapika: "Model Pikapika",
        maimai_classic: "maimai FiNALE / pra-DX",
        sdvx_nemsys: "NEMSYS (standard)",
        ddr_universal: "Universal Model (EU/NA)",
        ddr_legacy: "Kabinet CRT legasi",
        other_game: "Lain-lain",
      },
      ui: {
        shown: "{n} dipaparkan",
        stores_total: "{n} kedai jumlah",
        per_credit: "per kredit",
        show_more: "Tunjuk lagi",
        show_less: "Tunjuk kurang",
        search_wide: "Cari game, arked, tempat...",
        search_narrow: "Cari...",
        cab_model_unpublished: "Cabinet model not published",
        cab_model_unpublished_cap: "No listing says which cabinet this store runs. Official cab data covers Japan only, and community listings record the model just when someone noted it - so this is \"unknown\", not \"standard\".",
        offline_cab: "offline cabinet",
        offline_cabs: "offline cabinets",
        offline_cap: "This cabinet's network has shut down. It can still be played, but nothing is saved: no score history, no online play, no unlocks.",
        price_median: "{game}, median of {n} quoted prices in {country}. Not this store's own price.",
        price_sparse: "Based on only {n} listing(s) in {country}{for_game}, so treat it as a rough guide.",
        for_game: " for {game}",
        typical_country: "Typical for {country} - not this store's own price",
        permanently_closed: "Ditutup kekal.",
        source: "sumber",
        photo_by: "photo: {credit}",
        unknown_author: "unknown",
        size_1: "1 to 2 cabinets",
        size_2: "3 to 9 cabinets",
        size_3: "10 to 19 cabinets",
        size_4: "20 to 49 cabinets",
        size_5: "50 or more cabinets (mega arcade)",
        size_U: "Count unknown",
      }
    },

    th: {
      app: { title: "แผนที่อาร์เคด", updated: "อัปเดต {date}", data_failed: "โหลดข้อมูลไม่สำเร็จ" },
      drawer: { toggle: "สลับตัวกรอง", toggle_title: "สลับแผงตัวกรอง" },
      meta: { updated_title: "ข้อมูลอัปเดตล่าสุด", count_title: "หมุดที่แสดง / ร้านที่วางบนแผนที่ได้" },
      search: { placeholder: "ค้นหาชื่อหรือที่อยู่...", aria: "ค้นหาอาร์เคดด้วยชื่อหรือที่อยู่" },
      repo: { title: "ที่เก็บ GitHub", aria: "ที่เก็บ GitHub" },
      tab: { filters: "ตัวกรอง", china: "รายการไม่มีพิกัด" },
      pane: { games: "เกม", cab_variants: "รุ่นตู้",
        arcade_size: "ขนาดอาร์เคด" },
      btn: { all: "ทั้งหมด", none: "ไม่มี" },
      hint: {
        cab_variant: "เลือกตัวแปรจะจำกัดหมุดเกมนั้นเหลือเฉพาะร้านที่มีตู้นั้น",
        arcade_size: "ช่วงจำนวนตู้ตรงกับรูปหมุดบนแผนที่ ไม่ทราบหมายถึงไม่มีจำนวนที่เชื่อถือได้ถูกเผยแพร่",
        china1: "ร้านที่ไม่มีพิกัดแผนที่ (ส่วนใหญ่จีน)",
        china2: "จากรายการ WAHLAP อย่างเป็นทางการและแผนที่ชุมชน BemaniCN (มีแต่ที่อยู่) ค้นหาที่อยู่ในแอปแผนที่ แผนที่เว็บจีนใช้ GCJ-02 จุดจีนบนแผนที่แปลงเป็น WGS-84 แล้ว (โดยประมาณ)"
      },
      nearby: {
        title: "อาร์เคดใกล้เคียง", close: "ปิด", close_aria: "ปิดรายการใกล้เคียง", pane_aria: "อาร์เคดใกล้เคียง",
        search_area: "ค้นหาพื้นที่นี้", empty: "ไม่มีร้านตรงกับตัวกรอง เปิดเกมหรือแหล่งข้อมูลอีกครั้ง",
        nearest_you: "ใกล้ตำแหน่งของคุณที่สุด", nearest_to: "ใกล้ {label} ที่สุด",
        showing: "แสดง {n} ร้านใกล้สุดที่ตรงตัวกรอง ร้านไม่มีพิกัดไม่แสดง",
        no_coords_note: "ร้านไม่มีพิกัดไม่แสดง", locate: "แสดงอาร์เคดใกล้ฉัน",
        your_location: "ตำแหน่งของคุณ", this_point: "จุดนี้"
      },
      map: { aria: "แผนที่อาร์เคด" },
      empty: { map: "ไม่มีอาร์เคดตรงกับตัวกรอง" },
      foot: { data_sources: "แหล่งข้อมูล", sources: "แหล่ง", show: "แสดงจำนวนแหล่งข้อมูล", hide: "ซ่อนจำนวนแหล่งข้อมูล" },
      lang: { button: "ภาษา", menu: "เลือกภาษา" },
      settings: {
        title: "การตั้งค่า", close: "ปิดการตั้งค่า", sections: "ส่วนการตั้งค่า", gear: "การตั้งค่า",
        sec_sources: "แหล่งข้อมูล", sec_display: "การแสดงผล", sec_location: "ตำแหน่ง", sec_about: "เกี่ยวกับ",
        sources_head: "แหล่งข้อมูล",
        sources_note: "ปิดแหล่งเพื่อซ่อนร้าน ร้านที่อยู่ในหลายแหล่งจะยังแสดงถ้ามีแหล่งใดเปิดอยู่",
        display_head: "การแสดงผล",
        marker_scaling: "ขนาดหมุดตามจำนวนตู้",
        marker_scaling_desc: "ร้านที่มีตู้เยอะกว่าจะใหญ่กว่า ปิดแล้วหมุดทุกอันขนาดเท่ากัน (รูปร่างยังบอกระดับ)",
        location_head: "ตำแหน่ง",
        location_enabled: "เปิดใช้ฟีเจอร์ตำแหน่ง",
        location_enabled_desc: "แสดงปุ่มระบุตำแหน่งและรายการอาร์เคดใกล้คุณ",
        location_privacy: "ตำแหน่งของคุณไม่ออกจากเบราว์เซอร์",
        location_privacy_body: " อ่านเมื่อคุณขอเท่านั้น ใช้เรียงระยะบนหน้านี้ และไม่อัปโหลด เก็บ หรือแชร์ ไซต์นี้ไม่มีเซิร์ฟเวอร์และวิเคราะห์",
        legend: "คำอธิบายสัญลักษณ์",
        icon_cabinets: "ไอคอน: จำนวนตู้รวมของร้าน",
        tier_unknown: "ไม่ทราบจำนวน (วาดขนาดกลาง)",
        cluster_note: "คลัสเตอร์ 12 ร้าน ขอบทองหมายถึงมีร้าน 20+ ตู้ข้างใน",
        legend_note: "แต่ละระดับรูปต่างกัน รายการทางการส่วนใหญ่มีเกมแต่ไม่มีจำนวนตู้ ดังนั้นจำนวนไม่ทราบใช้ไอคอนกลางแยก (หมายถึงยังไม่เผยแพร่ ไม่ใช่ตู้เดียว) จำนวนจาก BemaniCN และ ZIv เมื่อมี ขนาดตามการแสดงผล รูปคงที่",
        icon_color: "สีไอคอน: เกมของร้าน",
        color_note: "ร้านหลายเกมใช้สีเกมที่เลือกอันแรกตามลำดับด้านล่าง ด้านบนเป็นสีตัวอย่าง บนแผนที่ใช้สีเกมของร้าน",
        badges: "ป้ายในป๊อปอัปร้าน",
        cab_badge: "ป้ายเหลืองคือชื่อตู้ ไม่ใช่เกม: Lightning IIDX, Valkyrie/NEMSYS SOUND VOLTEX, DDR gold & Universal, GITADORA Arena, pop'n Pikapika และ Taiko รุ่นภูมิภาค",
        dead_badge: "ป้ายขีดฆ่าคือตู้ออฟไลน์: maimai FiNALE และ DDR ก่อน LCD ยังเล่นได้ แต่เครือข่ายปิดแล้ว - ไม่มีคะแนน ปลดล็อก หรือออนไลน์",
        badge_note: "ที่มาข้อมูลตู้และข้อจำกัด รายการทางการเผยแพร่รุ่นเฉพาะญี่ปุ่น นอกนั้นจากชุมชน ป้ายหาย = ยังไม่มีใครบันทึกรุ่น ไม่ใช่ตู้มาตรฐาน",
        about_map: "เกี่ยวกับแผนที่นี้",
        stats: "{stores} ร้าน มีพิกัด {plottable} อัปเดตข้อมูล {updated}",
        link_source: "ซอร์สโค้ดบน GitHub", link_data: "แหล่งข้อมูล", link_license: "สัญญาอนุญาต MIT",
        osm_note: "ข้อมูลแผนที่ (c) ผู้มีส่วนร่วม OpenStreetMap, ODbL รายการร้านเป็นของแหล่งต้นทาง พิกัดจีนแปลงจาก GCJ-02 (โดยประมาณ)",
        shown: "แสดง {n} จาก {total} ร้านที่วางแผนที่ได้ด้วยตัวกรองปัจจุบัน",
        src_extra: "แหล่งข้อมูลเพิ่มเติม",
        src_count_title: "ร้านจากแหล่งนี้ รวมที่ไม่มีพิกัด"
      },
      legend: {
        toggle: "คำอธิบาย", icon_cabinets: "ไอคอน: ตู้ที่ร้าน", color_game: "สี: เกม",
        full: "คำอธิบายเต็มในการตั้งค่า", unknown_title: "ไม่ทราบจำนวน ขนาดกลาง"
      },
      src: {
        allnet_name: "ALL.Net", allnet_desc: "ค้นหาร้านทางการ SEGA: maimai DX, CHUNITHM, O.N.G.E.K.I.",
        eagate_name: "e-amusement", eagate_desc: "ค้นหาร้านทางการ KONAMI: IIDX, SOUND VOLTEX, DDR และ Bemani อื่น",
        wahlap_name: "WAHLAP", wahlap_desc: "ตัวแทนจำหน่าย SEGA ทางการในจีนแผ่นดินใหญ่ มีแต่ที่อยู่ ไม่มีพิกัด",
        bemanicn_name: "BemaniCN", bemanicn_desc: "แผนที่ชุมชนตู้ Bemani ในจีนแผ่นดินใหญ่",
        ziv_name: "Zenius-I-Vanisher", ziv_desc: "ฐานข้อมูลอาร์เคดชุมชนครอบคลุมทั่วโลก",
        round1usa_name: "Round1 USA", round1usa_desc: "รายการสถานที่ Round1 ทางการในสหรัฐฯ",
        community_name: "Community", community_desc: "รายการที่คัดเองในที่เก็บนี้"
      },
      place: {
        directions: "เส้นทาง", nearby: "ใกล้เคียง", share: "แชร์", filters: "ตัวกรอง",
        close: "ปิดรายละเอียดสถานที่", details: "รายละเอียดสถานที่",
        address_copied: "คัดลอกที่อยู่แล้ว", link_copied: "คัดลอกลิงก์แล้ว", copy_failed: "คัดลอกไม่สำเร็จ",
        tap_to_copy: "แตะเพื่อคัดลอก",
        listed_by: "แหล่งที่ลงข้อมูล",
        no_map_position: "ร้านนี้ไม่มีตำแหน่งบนแผนที่",
        no_map_position_cap: "เผยแพร่เฉพาะที่อยู่ ใช้「เส้นทาง」เพื่อค้นหา",
        community_from: "ข้อมูลชุมชนจาก {src} อาจล้าสมัย{date}",
        community_listings: "รายการชุมชน",
        rechecked_community: "ตรวจซ้ำที่ {host} ยังเป็นข้อมูลชุมชน",
        checked_operator: "ตรวจเทียบกับ {host}",
        checked_operator_generic: "ตรวจเทียบกับหน้าเว็บทางการของผู้ให้บริการ",
        price_common: "ราคาที่พบบ่อยที่สุดใน {n} ตู้ที่ระบุไว้ที่นี่",
        per_machine: "ต่อตู้ ตามรายการ",
        machine_list_no_counts: "มีรายชื่อตู้ แต่ไม่มีจำนวน",
        machine_list_no_counts_cap: "รายการชุมชนระบุชื่อตู้ด้านล่างโดยไม่บอกว่ามีกี่ตู้แต่ละชนิด จึงเป็นขอบล่าง ไม่ใช่การนับจริง",
        cab_counts_unavailable: "ไม่มีข้อมูลจำนวนตู้",
        cab_counts_unavailable_cap: "แหล่งของร้านนี้ไม่เผยแพร่จำนวนตู้",
        approx_address: "ตำแหน่งจากที่อยู่",
        approx_address_cap: "แหล่งไม่มีพิกัด จึงจีโอโค้ดจากที่อยู่ที่พิมพ์ไว้",
        approx_street: "ตำแหน่งจากที่อยู่ (ระดับถนน)",
        approx_street_cap: "จีโอโค้ดถึงถนน ไม่ใช่ตัวอาคาร อาจคลาดหนึ่ง-สองประตู",
        approx_district: "ตำแหน่งโดยประมาณ (ระดับเขต)",
        approx_district_cap: "ไม่มีพิกัด หมุดอยู่กลางเขตในที่อยู่ ไม่ใช่ร้าน",
        approx_city: "ตำแหน่งโดยประมาณ (ระดับเมือง)",
        approx_city_cap: "ไม่มีพิกัดและไม่มีชื่อเขต หมุดอยู่กลางเมือง",
        back_to: "กลับไป{label}",
        search_gmaps: "ค้นหาใน Google Maps",
      },
      nb: {
        err_denied: "ถูกปฏิเสธสิทธิ์ตำแหน่ง อนุญาตในตั้งค่าเบราว์เซอร์แล้วลองใหม่",
        err_unavailable: "ใช้ตำแหน่งไม่ได้ตอนนี้ ลองใหม่หรือค้นหาเมือง",
        err_timeout: "ดึงตำแหน่งนานเกินไป ลองใหม่",
        err_generic: "ดึงตำแหน่งไม่ได้",
        err_empty: "ตำแหน่งว่าง ลองใหม่ในอีกสักครู่",
        err_off: "ปิดตำแหน่งในการตั้งค่าแล้ว",
        err_https: "ตำแหน่งต้องใช้การเชื่อมต่อที่ปลอดภัย (https)",
        err_unsupported: "เบราว์เซอร์นี้รายงานตำแหน่งไม่ได้"
      },
      cabs: {
        sdvx_vm: "รุ่น Valkyrie",
        iidx_lm: "รุ่น Lightning",
        ddr_gold: "ตู้ทองคำ (20 ปี)",
        gitadora_arena: "รุ่น Arena",
        popn_pikapika: "รุ่น Pikapika",
        maimai_classic: "maimai FiNALE / ก่อน DX",
        sdvx_nemsys: "NEMSYS (มาตรฐาน)",
        ddr_universal: "Universal Model (EU/NA)",
        ddr_legacy: "ตู้ CRT รุ่นเก่า",
        other_game: "อื่นๆ",
      },
      ui: {
        shown: "แสดง {n}",
        stores_total: "ร้านทั้งหมด {n}",
        per_credit: "ต่อครดิต",
        show_more: "แสดงเพิ่ม",
        show_less: "แสดงน้อยลง",
        search_wide: "ค้นหาเกม อาร์เคด สถานที่...",
        search_narrow: "ค้นหา...",
        cab_model_unpublished: "Cabinet model not published",
        cab_model_unpublished_cap: "No listing says which cabinet this store runs. Official cab data covers Japan only, and community listings record the model just when someone noted it - so this is \"unknown\", not \"standard\".",
        offline_cab: "offline cabinet",
        offline_cabs: "offline cabinets",
        offline_cap: "This cabinet's network has shut down. It can still be played, but nothing is saved: no score history, no online play, no unlocks.",
        price_median: "{game}, median of {n} quoted prices in {country}. Not this store's own price.",
        price_sparse: "Based on only {n} listing(s) in {country}{for_game}, so treat it as a rough guide.",
        for_game: " for {game}",
        typical_country: "Typical for {country} - not this store's own price",
        permanently_closed: "ปิดถาวร.",
        source: "แหล่ง",
        photo_by: "photo: {credit}",
        unknown_author: "unknown",
        size_1: "1 to 2 cabinets",
        size_2: "3 to 9 cabinets",
        size_3: "10 to 19 cabinets",
        size_4: "20 to 49 cabinets",
        size_5: "50 or more cabinets (mega arcade)",
        size_U: "Count unknown",
      }
    },

    vi: {
      app: { title: "Bản đồ Arcade", updated: "cập nhật {date}", data_failed: "tải dữ liệu thất bại" },
      drawer: { toggle: "Bật/tắt bộ lọc", toggle_title: "Bật/tắt bảng bộ lọc" },
      meta: { updated_title: "Dữ liệu cập nhật lần cuối", count_title: "Đánh dấu hiển thị / cửa hàng vẽ được" },
      search: { placeholder: "Tìm tên hoặc địa chỉ...", aria: "Tìm arcade theo tên hoặc địa chỉ" },
      repo: { title: "Kho GitHub", aria: "Kho GitHub" },
      tab: { filters: "Bộ lọc", china: "Danh sách không tọa độ" },
      pane: { games: "Trò chơi", cab_variants: "Biến thể máy",
        arcade_size: "Quy mô arcade" },
      btn: { all: "tất cả", none: "không" },
      hint: {
        cab_variant: "Chọn biến thể sẽ giới hạn đánh dấu game đó chỉ còn cửa hàng có máy đó.",
        arcade_size: "Các dải số máy khớp hình đánh dấu bản đồ. Không rõ nghĩa là chưa có số đã công bố đáng tin.",
        china1: "Cửa hàng không có tọa độ bản đồ (chủ yếu Trung Quốc).",
        china2: "Từ danh sách chính thức WAHLAP và bản đồ cộng đồng BemaniCN (chỉ địa chỉ). Tìm địa chỉ trong ứng dụng bản đồ. Bản đồ web Trung Quốc dùng GCJ-02; điểm Trung Quốc trên bản đồ đã chuyển sang WGS-84 (xấp xỉ)."
      },
      nearby: {
        title: "Arcade gần đây", close: "đóng", close_aria: "Đóng danh sách gần đây", pane_aria: "Arcade gần đây",
        search_area: "Tìm khu vực này", empty: "Không có cửa hàng khớp bộ lọc. Bật lại game hoặc nguồn.",
        nearest_you: "Gần vị trí của bạn nhất", nearest_to: "Gần {label} nhất",
        showing: "Hiển thị {n} cửa hàng gần nhất khớp bộ lọc. Không tọa độ thì không hiện.",
        no_coords_note: "Cửa hàng không tọa độ không được hiển thị.", locate: "Hiện arcade gần tôi",
        your_location: "vị trí của bạn", this_point: "điểm này"
      },
      map: { aria: "Bản đồ arcade" },
      empty: { map: "Không có arcade khớp bộ lọc" },
      foot: { data_sources: "nguồn dữ liệu", sources: "nguồn", show: "Hiện số nguồn dữ liệu", hide: "Ẩn số nguồn dữ liệu" },
      lang: { button: "Ngôn ngữ", menu: "Chọn ngôn ngữ" },
      settings: {
        title: "Cài đặt", close: "Đóng cài đặt", sections: "Phần cài đặt", gear: "Cài đặt",
        sec_sources: "Nguồn", sec_display: "Hiển thị", sec_location: "Vị trí", sec_about: "Giới thiệu",
        sources_head: "Nguồn dữ liệu",
        sources_note: "Tắt nguồn để ẩn cửa hàng của nó. Cửa hàng ở nhiều nguồn vẫn hiện khi còn một nguồn bật.",
        display_head: "Hiển thị",
        marker_scaling: "Cỡ đánh dấu theo số máy",
        marker_scaling_desc: "Cửa hàng đông máy vẽ lớn hơn. Tắt để mọi đánh dấu cùng cỡ (hình vẫn thể hiện bậc).",
        location_head: "Vị trí",
        location_enabled: "Bật tính năng vị trí",
        location_enabled_desc: "Hiện nút định vị và danh sách arcade gần bạn nhất.",
        location_privacy: "Vị trí của bạn không rời trình duyệt.",
        location_privacy_body: " Chỉ đọc khi bạn yêu cầu, dùng sắp xếp khoảng cách trên trang này, không tải lên, lưu hay chia sẻ. Site không có máy chủ và phân tích.",
        legend: "Chú giải",
        icon_cabinets: "Biểu tượng: tổng số máy tại cửa hàng",
        tier_unknown: "Số lượng không rõ (vẽ cỡ trung)",
        cluster_note: "Cụm 12 cửa hàng. Viền vàng nghĩa là có ít nhất một cửa hàng 20+ máy bên trong.",
        legend_note: "Mỗi bậc hình khác nhau. Hầu hết danh sách chính thức có game nhưng không có số máy, nên số không rõ dùng biểu tượng trung riêng (\"chưa công bố\", không phải \"một máy\"). Số từ BemaniCN và ZIv khi có. Cỡ theo cài đặt hiển thị; hình cố định.",
        icon_color: "Màu biểu tượng: game tại cửa hàng",
        color_note: "Cửa hàng nhiều game lấy màu game đã chọn đầu tiên theo thứ tự dưới. Chú giải trên dùng màu mẫu; trên bản đồ theo màu game cửa hàng.",
        badges: "Huy hiệu trong popup cửa hàng",
        cab_badge: "Huy hiệu vàng đặt tên MÁY, không phải game: Lightning IIDX, Valkyrie/NEMSYS SOUND VOLTEX, DDR gold & Universal, GITADORA Arena, pop'n Pikapika, và bản vùng Taiko.",
        dead_badge: "Huy hiệu gạch ngang là máy OFFLINE: maimai FiNALE và DDR trước LCD vẫn chơi được nhưng mạng đã tắt - không điểm, mở khóa hay online.",
        badge_note: "Nguồn dữ liệu máy và giới hạn. Danh sách nhà vận hành chỉ Nhật; ngoài đó từ cộng đồng. Thiếu huy hiệu = chưa ghi model, không phải máy chuẩn.",
        about_map: "Về bản đồ này",
        stats: "{stores} cửa hàng, {plottable} có tọa độ. Dữ liệu cập nhật {updated}.",
        link_source: "Mã nguồn trên GitHub", link_data: "Nguồn dữ liệu", link_license: "Giấy phép MIT",
        osm_note: "Dữ liệu bản đồ (c) cộng tác viên OpenStreetMap, ODbL. Danh sách cửa hàng thuộc nguồn tương ứng. Tọa độ Trung Quốc chuyển từ GCJ-02 (xấp xỉ).",
        shown: "{n} / {total} cửa hàng vẽ được hiển thị với bộ lọc hiện tại.",
        src_extra: "Nguồn dữ liệu bổ sung.",
        src_count_title: "cửa hàng từ nguồn này, gồm không tọa độ"
      },
      legend: {
        toggle: "Chú giải", icon_cabinets: "Biểu tượng: máy tại cửa hàng", color_game: "Màu: game",
        full: "Chú giải đầy đủ trong Cài đặt", unknown_title: "số không rõ, cỡ trung"
      },
      src: {
        allnet_name: "ALL.Net", allnet_desc: "Tìm cửa hàng chính thức SEGA: maimai DX, CHUNITHM, O.N.G.E.K.I.",
        eagate_name: "e-amusement", eagate_desc: "Tìm cửa hàng chính thức KONAMI: IIDX, SOUND VOLTEX, DDR và Bemani khác.",
        wahlap_name: "WAHLAP", wahlap_desc: "Nhà phân phối SEGA chính thức Trung Quốc đại lục. Chỉ địa chỉ, không tọa độ.",
        bemanicn_name: "BemaniCN", bemanicn_desc: "Bản đồ cộng đồng máy Bemani ở Trung Quốc đại lục.",
        ziv_name: "Zenius-I-Vanisher", ziv_desc: "CSDL arcade cộng đồng phủ toàn cầu.",
        round1usa_name: "Round1 USA", round1usa_desc: "Danh sách địa điểm Round1 chính thức Hoa Kỳ.",
        community_name: "Community", community_desc: "Mục được biên soạn tay trong kho này."
      },
      place: {
        directions: "Chỉ đường", nearby: "Gần đây", share: "Chia sẻ", filters: "Bộ lọc",
        close: "Đóng chi tiết địa điểm", details: "Chi tiết địa điểm",
        address_copied: "Đã sao chép địa chỉ", link_copied: "Đã sao chép liên kết", copy_failed: "Sao chép thất bại",
        tap_to_copy: "Chạm để sao chép",
        listed_by: "Được liệt kê bởi",
        no_map_position: "Cửa hàng này không có vị trí trên bản đồ",
        no_map_position_cap: "Chỉ công bố địa chỉ. Dùng Chỉ đường để tìm.",
        community_from: "dữ liệu cộng đồng từ {src}, có thể lỗi thời{date}",
        community_listings: "danh sách cộng đồng",
        rechecked_community: "đã kiểm tra lại trên {host}, vẫn là dữ liệu cộng đồng",
        checked_operator: "đã đối chiếu với {host}",
        checked_operator_generic: "đã đối chiếu với trang chính thức của nhà vận hành",
        price_common: "Giá phổ biến nhất trong {n} máy được liệt kê tại đây.",
        per_machine: "Mỗi máy, theo danh sách.",
        machine_list_no_counts: "Có danh sách máy, không có số lượng cabinet",
        machine_list_no_counts_cap: "Danh sách cộng đồng nêu tên máy bên dưới mà không nói mỗi loại có bao nhiêu, nên đây là giới hạn dưới chứ không phải kiểm kê.",
        cab_counts_unavailable: "Không có số lượng cabinet",
        cab_counts_unavailable_cap: "Nguồn của cửa hàng này không công bố số máy.",
        approx_address: "Vị trí từ địa chỉ",
        approx_address_cap: "Nguồn không có tọa độ; ghim được geocode từ địa chỉ in.",
        approx_street: "Vị trí từ địa chỉ (cấp đường)",
        approx_street_cap: "Geocode tới đường chứ không phải tòa nhà; có thể lệch một-hai cửa.",
        approx_district: "Vị trí xấp xỉ (cấp quận)",
        approx_district_cap: "Không tọa độ; ghim ở trung tâm quận trong địa chỉ, không phải cửa hàng.",
        approx_city: "Vị trí xấp xỉ (cấp thành phố)",
        approx_city_cap: "Không tọa độ và không tên quận; ghim ở trung tâm thành phố.",
        back_to: "Quay lại {label}",
        search_gmaps: "Tìm trên Google Maps",
      },
      nb: {
        err_denied: "Quyền vị trí bị từ chối. Cho phép trong cài đặt trình duyệt rồi thử lại.",
        err_unavailable: "Vị trí hiện không khả dụng. Thử lại hoặc tìm thành phố.",
        err_timeout: "Lấy vị trí quá lâu. Thử lại.",
        err_generic: "Không lấy được vị trí của bạn.",
        err_empty: "Vị trí trống. Thử lại sau.",
        err_off: "Vị trí đang tắt trong cài đặt.",
        err_https: "Vị trí cần kết nối an toàn (https).",
        err_unsupported: "Trình duyệt này không báo được vị trí."
      },
      cabs: {
        sdvx_vm: "Model Valkyrie",
        iidx_lm: "Model Lightning",
        ddr_gold: "Cabinet vàng (20 năm)",
        gitadora_arena: "Model Arena",
        popn_pikapika: "Model Pikapika",
        maimai_classic: "maimai FiNALE / trước DX",
        sdvx_nemsys: "NEMSYS (tiêu chuẩn)",
        ddr_universal: "Universal Model (EU/NA)",
        ddr_legacy: "Cabinet CRT cũ",
        other_game: "Khác",
      },
      ui: {
        shown: "{n} đang hiện",
        stores_total: "tổng {n} cửa hàng",
        per_credit: "mỗi credit",
        show_more: "Xem thêm",
        show_less: "Thu gọn",
        search_wide: "Tìm game, arcade, địa điểm...",
        search_narrow: "Tìm...",
        cab_model_unpublished: "Cabinet model not published",
        cab_model_unpublished_cap: "No listing says which cabinet this store runs. Official cab data covers Japan only, and community listings record the model just when someone noted it - so this is \"unknown\", not \"standard\".",
        offline_cab: "offline cabinet",
        offline_cabs: "offline cabinets",
        offline_cap: "This cabinet's network has shut down. It can still be played, but nothing is saved: no score history, no online play, no unlocks.",
        price_median: "{game}, median of {n} quoted prices in {country}. Not this store's own price.",
        price_sparse: "Based on only {n} listing(s) in {country}{for_game}, so treat it as a rough guide.",
        for_game: " for {game}",
        typical_country: "Typical for {country} - not this store's own price",
        permanently_closed: "Đã đóng vĩnh viễn.",
        source: "nguồn",
        photo_by: "photo: {credit}",
        unknown_author: "unknown",
        size_1: "1 to 2 cabinets",
        size_2: "3 to 9 cabinets",
        size_3: "10 to 19 cabinets",
        size_4: "20 to 49 cabinets",
        size_5: "50 or more cabinets (mega arcade)",
        size_U: "Count unknown",
      }
    },

    fil: {
      app: { title: "Arcade Maps", updated: "na-update {date}", data_failed: "nabigo ang pag-load ng data" },
      drawer: { toggle: "I-toggle ang mga filter", toggle_title: "I-toggle ang filter panel" },
      meta: { updated_title: "Huling na-update ang data", count_title: "Mga marker na ipinapakita / mapplot na tindahan" },
      search: { placeholder: "Maghanap ng pangalan o address...", aria: "Maghanap ng arcade ayon sa pangalan o address" },
      repo: { title: "GitHub repository", aria: "GitHub repository" },
      tab: { filters: "Mga filter", china: "Walang coords" },
      pane: { games: "Mga laro", cab_variants: "Mga variant ng cab",
        arcade_size: "Laki ng arcade" },
      btn: { all: "lahat", none: "wala" },
      hint: {
        cab_variant: "Ang pag-check ng variant ay nililimitahan ang mga marker ng larong iyon sa mga tindahang may cab.",
        arcade_size: "Ang mga banda ng bilang ng cabinet ay tumutugma sa hugis ng marker sa mapa. Unknown = walang mapagkakatiwalaang bilang na na-publish.",
        china1: "Mga tindahang walang coordinates sa mapa (karamihan sa China).",
        china2: "Mula sa opisyal na listahan ng WAHLAP at community map ng BemaniCN (address lang). Hanapin ang address sa map app. Gumagamit ang Chinese web maps ng GCJ-02; ang mga China point sa mapa ay na-convert sa WGS-84 (tinatayang)."
      },
      nearby: {
        title: "Mga malapit na arcade", close: "isara", close_aria: "Isara ang listahan ng malapit", pane_aria: "Mga malapit na arcade",
        search_area: "Hanapin ang lugar na ito", empty: "Walang tindahang tumutugma sa filter. Buksan muli ang laro o source.",
        nearest_you: "Pinakamalapit sa lokasyon mo", nearest_to: "Pinakamalapit sa {label}",
        showing: "Ipinapakita ang {n} pinakamalapit na tindahang tumutugma. Walang coords ay hindi ipinapakita.",
        no_coords_note: "Hindi ipinapakita ang mga tindahang walang coordinates.", locate: "Ipakita ang mga arcade malapit sa akin",
        your_location: "iyong lokasyon", this_point: "puntong ito"
      },
      map: { aria: "Mapa ng arcade" },
      empty: { map: "Walang arcade na tumutugma sa mga filter" },
      foot: { data_sources: "mga pinagmumulan ng data", sources: "sources", show: "Ipakita ang bilang ng data source", hide: "Itago ang bilang ng data source" },
      lang: { button: "Wika", menu: "Pumili ng wika" },
      settings: {
        title: "Mga setting", close: "Isara ang settings", sections: "Mga seksyon ng settings", gear: "Mga setting",
        sec_sources: "Sources", sec_display: "Display", sec_location: "Lokasyon", sec_about: "Tungkol",
        sources_head: "Mga pinagmumulan ng data",
        sources_note: "I-off ang source para itago ang mga tindahan nito. Ang tindahan sa maraming source ay nananatili habang may bukas na isa.",
        display_head: "Display",
        marker_scaling: "Laki ng marker ayon sa bilang ng cabinet",
        marker_scaling_desc: "Mas abalang tindahan ay mas malaki. I-off para pareho ang laki ng lahat (hugis pa rin ang tier).",
        location_head: "Lokasyon",
        location_enabled: "I-enable ang location features",
        location_enabled_desc: "Ipakita ang locate button at listahan ng pinakamalapit na arcade.",
        location_privacy: "Hindi umaalis sa browser ang lokasyon mo.",
        location_privacy_body: " Binabasa lang pag humiling ka, ginagamit sa page na ito para i-sort ang distansya, at hindi inu-upload, sine-save, o sine-share. Walang server o analytics ang site na ito.",
        legend: "Legend",
        icon_cabinets: "Icon: kabuuang cabinets sa tindahan",
        tier_unknown: "Hindi alam ang bilang (mid-size)",
        cluster_note: "Cluster ng 12 tindahan. Ang gintong rim ay nangangahulugang may 20+ cabinet na tindahan sa loob.",
        legend_note: "Iba ang hugis ng bawat tier. Karamihan sa opisyal na listahan ay may laro pero walang bilang ng cabinet, kaya ang unknown ay may sariling mid icon (\"hindi nai-publish\", hindi \"isang cabinet\"). Bilang mula sa BemaniCN at ZIv kung may data. Laki ayon sa Display; hugis ay fixed.",
        icon_color: "Kulay ng icon: laro sa tindahan",
        color_note: "Ang tindahang may ilang laro ay kumukuha ng kulay ng unang napiling laro sa order sa ibaba. Sample color ang legend sa itaas; sa mapa ay kulay ng laro ng tindahan.",
        badges: "Mga badge sa store popup",
        cab_badge: "Ang yellow badges ay pangalan ng CABINET, hindi laro: Lightning IIDX, Valkyrie/NEMSYS SOUND VOLTEX, DDR gold at Universal, GITADORA Arena, pop'n Pikapika, at regional Taiko.",
        dead_badge: "Ang may strike-through ay OFFLINE cabinet: gumagana pa ang maimai FiNALE at pre-LCD DDR, pero sarado na ang network - walang scores, unlocks, o online.",
        badge_note: "Saan galing ang cabinet data at limitasyon nito. Opisyal na operator lists ay Japan lang; sa labas ay community lists. Missing badge = walang nag-record ng model, hindi standard cabinet.",
        about_map: "Tungkol sa mapang ito",
        stats: "{stores} na tindahan, {plottable} may coordinates. Data updated {updated}.",
        link_source: "Source code sa GitHub", link_data: "Mga pinagmumulan ng data", link_license: "MIT license",
        osm_note: "Map data (c) OpenStreetMap contributors, ODbL. Pag-aari ng kani-kanilang sources ang store listings. China coordinates mula sa GCJ-02 (tinatayang).",
        shown: "{n} sa {total} mapplot na tindahan ang ipinapakita sa kasalukuyang filters.",
        src_extra: "Karagdagang data source.",
        src_count_title: "mga tindahan mula sa source na ito, kasama ang walang coordinates"
      },
      legend: {
        toggle: "Legend", icon_cabinets: "Icon: cabinets sa tindahan", color_game: "Kulay: laro",
        full: "Buong legend sa Settings", unknown_title: "hindi alam ang bilang, mid-size"
      },
      src: {
        allnet_name: "ALL.Net", allnet_desc: "Opisyal na SEGA store locator: maimai DX, CHUNITHM, O.N.G.E.K.I.",
        eagate_name: "e-amusement", eagate_desc: "Opisyal na KONAMI store locator: IIDX, SOUND VOLTEX, DDR at iba pang Bemani.",
        wahlap_name: "WAHLAP", wahlap_desc: "Opisyal na SEGA distributor sa mainland China. Address lang, walang coordinates.",
        bemanicn_name: "BemaniCN", bemanicn_desc: "Community map ng Bemani cabinets sa mainland China.",
        ziv_name: "Zenius-I-Vanisher", ziv_desc: "Community arcade database na may worldwide coverage.",
        round1usa_name: "Round1 USA", round1usa_desc: "Opisyal na listahan ng Round1 venue sa United States.",
        community_name: "Community", community_desc: "Mga entry na manu-manong na-curate sa repository na ito."
      },
      place: {
        directions: "Direksyon", nearby: "Malapit", share: "I-share", filters: "Mga filter",
        close: "Isara ang detalye ng lugar", details: "Detalye ng lugar",
        address_copied: "Nakopya ang address", link_copied: "Nakopya ang link", copy_failed: "Nabigo ang pag-copy",
        tap_to_copy: "I-tap para kopyahin",
        listed_by: "Nakalista mula sa",
        no_map_position: "Walang posisyon sa mapa ang tindahang ito",
        no_map_position_cap: "Address lang ang na-publish. Gamitin ang Direksyon para maghanap.",
        community_from: "community data mula sa {src}, maaaring luma{date}",
        community_listings: "mga community listing",
        rechecked_community: "muling sinuri sa {host}, community data pa rin",
        checked_operator: "sinuri laban sa {host}",
        checked_operator_generic: "sinuri laban sa opisyal na listahan ng operator",
        price_common: "Pinakakaraniwang presyo sa {n} makinang nakalista rito.",
        per_machine: "Bawat makina, ayon sa listahan.",
        machine_list_no_counts: "May listahan ng makina, walang bilang ng cabinet",
        machine_list_no_counts_cap: "Pinangalanan ng community listing ang mga makina sa ibaba nang hindi sinasabi kung ilan ang bawat isa, kaya ito ay lower bound, hindi buong bilang.",
        cab_counts_unavailable: "Walang bilang ng cabinet",
        cab_counts_unavailable_cap: "Hindi nagpa-publish ang mga pinagmulan ng bilang ng makina.",
        approx_address: "Posisyon mula sa address",
        approx_address_cap: "Walang coordinates ang source; na-geocode ang pin mula sa naka-print na address.",
        approx_street: "Posisyon mula sa address (level ng kalsada)",
        approx_street_cap: "Na-geocode sa kalsada, hindi gusali; maaaring malayo ng isa-dalawang pinto.",
        approx_district: "Tinatayang posisyon (level ng distrito)",
        approx_district_cap: "Walang coordinates; ang pin ay gitna ng distrito sa address, hindi ang tindahan.",
        approx_city: "Tinatayang posisyon (level ng lungsod)",
        approx_city_cap: "Walang coordinates at walang pangalan ng distrito; gitna ng lungsod ang pin.",
        back_to: "Bumalik sa {label}",
        search_gmaps: "Hanapin sa Google Maps",
      },
      nb: {
        err_denied: "Tinanggihan ang pahintulot sa lokasyon. Payagan sa browser settings, tapos subukan ulit.",
        err_unavailable: "Hindi available ang lokasyon ngayon. Subukan ulit, o maghanap ng lungsod.",
        err_timeout: "Masyadong matagal ang pagkuha ng lokasyon. Subukan ulit.",
        err_generic: "Hindi makuha ang lokasyon mo.",
        err_empty: "Walang laman ang lokasyon. Subukan ulit sa ilang sandali.",
        err_off: "Naka-off ang lokasyon sa settings.",
        err_https: "Kailangan ng secure (https) connection ang lokasyon.",
        err_unsupported: "Hindi kayang i-report ng browser na ito ang lokasyon."
      },
      cabs: {
        sdvx_vm: "Valkyrie model",
        iidx_lm: "Lightning model",
        ddr_gold: "Gold cab (20th anniv.)",
        gitadora_arena: "Arena model",
        popn_pikapika: "Pikapika model",
        maimai_classic: "maimai FiNALE / pre-DX",
        sdvx_nemsys: "NEMSYS (standard)",
        ddr_universal: "Universal Model (EU/NA)",
        ddr_legacy: "Legacy CRT cabinet",
        other_game: "Iba pa",
      },
      ui: {
        shown: "{n} ipinapakita",
        stores_total: "{n} na tindahan sa kabuuan",
        per_credit: "bawat credit",
        show_more: "Ipakita pa",
        show_less: "Magpakita ng mas kaunti",
        search_wide: "Maghanap ng laro, arcade, lugar...",
        search_narrow: "Maghanap...",
        cab_model_unpublished: "Cabinet model not published",
        cab_model_unpublished_cap: "No listing says which cabinet this store runs. Official cab data covers Japan only, and community listings record the model just when someone noted it - so this is \"unknown\", not \"standard\".",
        offline_cab: "offline cabinet",
        offline_cabs: "offline cabinets",
        offline_cap: "This cabinet's network has shut down. It can still be played, but nothing is saved: no score history, no online play, no unlocks.",
        price_median: "{game}, median of {n} quoted prices in {country}. Not this store's own price.",
        price_sparse: "Based on only {n} listing(s) in {country}{for_game}, so treat it as a rough guide.",
        for_game: " for {game}",
        typical_country: "Typical for {country} - not this store's own price",
        permanently_closed: "Permanenteng sarado.",
        source: "pinagmulan",
        photo_by: "photo: {credit}",
        unknown_author: "unknown",
        size_1: "1 to 2 cabinets",
        size_2: "3 to 9 cabinets",
        size_3: "10 to 19 cabinets",
        size_4: "20 to 49 cabinets",
        size_5: "50 or more cabinets (mega arcade)",
        size_U: "Count unknown",
      }
    },

    es: {
      app: { title: "Arcade Maps", updated: "actualizado {date}", data_failed: "error al cargar datos" },
      drawer: { toggle: "Alternar filtros", toggle_title: "Alternar panel de filtros" },
      meta: { updated_title: "Datos actualizados por última vez", count_title: "Marcadores mostrados / locales en mapa" },
      search: { placeholder: "Buscar nombre o dirección...", aria: "Buscar arcades por nombre o dirección" },
      repo: { title: "Repositorio de GitHub", aria: "Repositorio de GitHub" },
      tab: { filters: "Filtros", china: "Sin coordenadas" },
      pane: { games: "Juegos", cab_variants: "Variantes de cabina",
        arcade_size: "Tamaño del arcade" },
      btn: { all: "todos", none: "ninguno" },
      hint: {
        cab_variant: "Marcar una variante limita los marcadores de ese juego a locales con esa cabina.",
        arcade_size: "Las franjas de cabinas coinciden con las formas de los marcadores. Desconocido significa que no se publicó un recuento fiable.",
        china1: "Locales sin coordenadas en el mapa (sobre todo China).",
        china2: "De la lista oficial WAHLAP y el mapa comunitario BemaniCN (solo direcciones). Busca la dirección en tu app de mapas. Los mapas web chinos usan GCJ-02; los puntos de China en el mapa se convirtieron a WGS-84 (aproximados)."
      },
      nearby: {
        title: "Arcades cercanos", close: "cerrar", close_aria: "Cerrar lista cercana", pane_aria: "Arcades cercanos",
        search_area: "Buscar en esta zona", empty: "Ningún local coincide con los filtros. Activa de nuevo un juego o una fuente.",
        nearest_you: "Más cercanos a tu ubicación", nearest_to: "Más cercanos a {label}",
        showing: "Mostrando los {n} locales más cercanos que coinciden. Sin coordenadas no se muestran.",
        no_coords_note: "Los locales sin coordenadas no se muestran.", locate: "Mostrar arcades cerca de mí",
        your_location: "tu ubicación", this_point: "este punto"
      },
      map: { aria: "Mapa de arcades" },
      empty: { map: "Ningún arcade coincide con tus filtros" },
      foot: { data_sources: "fuentes de datos", sources: "fuentes", show: "Mostrar recuentos de fuentes", hide: "Ocultar recuentos de fuentes" },
      lang: { button: "Idioma", menu: "Elegir idioma" },
      settings: {
        title: "Ajustes", close: "Cerrar ajustes", sections: "Secciones de ajustes", gear: "Ajustes",
        sec_sources: "Fuentes", sec_display: "Pantalla", sec_location: "Ubicación", sec_about: "Acerca de",
        sources_head: "Fuentes de datos",
        sources_note: "Desactiva una fuente para ocultar sus locales. Un local en varias fuentes permanece si alguna está activa.",
        display_head: "Pantalla",
        marker_scaling: "Tamaño del marcador por número de cabinas",
        marker_scaling_desc: "Los locales con más cabinas se dibujan más grandes. Desactívalo para el mismo tamaño en todos (la forma sigue mostrando el nivel).",
        location_head: "Ubicación",
        location_enabled: "Activar funciones de ubicación",
        location_enabled_desc: "Muestra el botón de ubicación y la lista de arcades más cercanos.",
        location_privacy: "Tu ubicación nunca sale del navegador.",
        location_privacy_body: " Solo se lee cuando la pides, se usa en esta página para ordenar por distancia y nunca se sube, almacena ni comparte. Este sitio no tiene servidor ni analíticas.",
        legend: "Leyenda",
        icon_cabinets: "Icono: cabinas totales en el local",
        tier_unknown: "Cantidad desconocida (tamaño medio)",
        cluster_note: "Clúster de 12 locales. Un borde dorado indica al menos un local con 20+ cabinas.",
        legend_note: "Cada nivel tiene forma distinta. La mayoría de listados oficiales publican juegos pero no el número de cabinas, así que lo desconocido tiene un icono medio propio (\"no publicado\", no \"una cabina\"). Cifras de BemaniCN y ZIv cuando hay datos. El tamaño sigue Ajustes de pantalla; las formas no.",
        icon_color: "Color del icono: juego del local",
        color_note: "Un local con varios juegos toma el color del primer juego seleccionado en el orden de abajo. La leyenda superior usa un color de muestra; en el mapa, el del juego del local.",
        badges: "Insignias en el popup del local",
        cab_badge: "Las insignias amarillas nombran la CABINA, no el juego: Lightning IIDX, Valkyrie/NEMSYS SOUND VOLTEX, DDR gold y Universal, GITADORA Arena, pop'n Pikapika y builds regionales de Taiko.",
        dead_badge: "Una insignia tachada es una cabina OFFLINE: maimai FiNALE y DDR pre-LCD aún se juegan, pero sus redes cerraron: sin puntuaciones, desbloqueos ni online.",
        badge_note: "Origen de los datos de cabina y sus límites. Los listados oficiales publican modelos solo en Japón; fuera, de listas comunitarias. Insignia ausente = nadie registró el modelo, no \"cabina estándar\".",
        about_map: "Acerca de este mapa",
        stats: "{stores} locales, {plottable} con coordenadas. Datos actualizados {updated}.",
        link_source: "Código fuente en GitHub", link_data: "Fuentes de datos", link_license: "Licencia MIT",
        osm_note: "Datos del mapa (c) colaboradores de OpenStreetMap, ODbL. Los listados pertenecen a sus fuentes. Coordenadas de China convertidas desde GCJ-02 (aproximadas).",
        shown: "{n} de {total} locales en mapa con los filtros actuales.",
        src_extra: "Fuente de datos adicional.",
        src_count_title: "locales de esta fuente, incluidas entradas sin coordenadas"
      },
      legend: {
        toggle: "Leyenda", icon_cabinets: "Icono: cabinas en el local", color_game: "Color: juego",
        full: "Leyenda completa en Ajustes", unknown_title: "cantidad desconocida, tamaño medio"
      },
      src: {
        allnet_name: "ALL.Net", allnet_desc: "Localizador oficial SEGA: maimai DX, CHUNITHM, O.N.G.E.K.I.",
        eagate_name: "e-amusement", eagate_desc: "Localizador oficial KONAMI: IIDX, SOUND VOLTEX, DDR y otros Bemani.",
        wahlap_name: "WAHLAP", wahlap_desc: "Distribuidor oficial SEGA en China continental. Solo direcciones, sin coordenadas.",
        bemanicn_name: "BemaniCN", bemanicn_desc: "Mapa comunitario de cabinas Bemani en China continental.",
        ziv_name: "Zenius-I-Vanisher", ziv_desc: "Base de datos comunitaria de arcades con cobertura mundial.",
        round1usa_name: "Round1 USA", round1usa_desc: "Lista oficial de locales Round1 en Estados Unidos.",
        community_name: "Community", community_desc: "Entradas curadas a mano en este repositorio."
      },
      place: {
        directions: "Cómo llegar", nearby: "Cercanos", share: "Compartir", filters: "Filtros",
        close: "Cerrar detalles del lugar", details: "Detalles del lugar",
        address_copied: "Dirección copiada", link_copied: "Enlace copiado", copy_failed: "Error al copiar",
        tap_to_copy: "Toca para copiar",
        listed_by: "Listado por",
        no_map_position: "Este local no tiene posición en el mapa",
        no_map_position_cap: "Solo se publicó la dirección. Usa Cómo llegar para buscarla.",
        community_from: "datos de la comunidad de {src}; pueden estar desactualizados{date}",
        community_listings: "listados de la comunidad",
        rechecked_community: "vuelto a comprobar en {host}; sigue siendo dato comunitario",
        checked_operator: "comprobado con {host}",
        checked_operator_generic: "comprobado con el listado oficial del operador",
        price_common: "Precio más frecuente entre las {n} máquinas listadas aquí.",
        per_machine: "Por máquina, según el listado.",
        machine_list_no_counts: "Hay lista de máquinas, sin número de cabinas",
        machine_list_no_counts_cap: "El listado comunitario nombra las máquinas de abajo sin decir cuántas hay de cada una; es un mínimo, no un inventario.",
        cab_counts_unavailable: "Número de cabinas no disponible",
        cab_counts_unavailable_cap: "Las fuentes de este local no publican cuántas máquinas tiene.",
        approx_address: "Posición a partir de la dirección",
        approx_address_cap: "La fuente no da coordenadas; el pin se geocodificó desde la dirección impresa.",
        approx_street: "Posición a partir de la dirección (nivel calle)",
        approx_street_cap: "Geocodificado a la calle, no al edificio; puede fallar una o dos puertas.",
        approx_district: "Posición aproximada (nivel distrito)",
        approx_district_cap: "Sin coordenadas; el pin es el centro del distrito de la dirección, no el local.",
        approx_city: "Posición aproximada (nivel ciudad)",
        approx_city_cap: "Sin coordenadas ni nombre de distrito; el pin es el centro de la ciudad.",
        back_to: "Volver a {label}",
        search_gmaps: "Buscar en Google Maps",
      },
      nb: {
        err_denied: "Permiso de ubicación denegado. Permítelo en el navegador e inténtalo de nuevo.",
        err_unavailable: "Ubicación no disponible. Inténtalo de nuevo o busca una ciudad.",
        err_timeout: "La ubicación tardó demasiado. Inténtalo de nuevo.",
        err_generic: "No se pudo obtener tu ubicación.",
        err_empty: "La ubicación volvió vacía. Inténtalo en un momento.",
        err_off: "La ubicación está desactivada en ajustes.",
        err_https: "La ubicación necesita una conexión segura (https).",
        err_unsupported: "Este navegador no puede informar la ubicación."
      },
      cabs: {
        sdvx_vm: "Modelo Valkyrie",
        iidx_lm: "Modelo Lightning",
        ddr_gold: "Cabina dorada (20.º aniv.)",
        gitadora_arena: "Modelo Arena",
        popn_pikapika: "Modelo Pikapika",
        maimai_classic: "maimai FiNALE / pre-DX",
        sdvx_nemsys: "NEMSYS (estándar)",
        ddr_universal: "Universal Model (EU/NA)",
        ddr_legacy: "Cabina CRT antigua",
        other_game: "Otros",
      },
      ui: {
        shown: "{n} mostrados",
        stores_total: "{n} locales en total",
        per_credit: "por crédito",
        show_more: "Mostrar más",
        show_less: "Mostrar menos",
        search_wide: "Buscar juegos, arcades, lugares...",
        search_narrow: "Buscar...",
        cab_model_unpublished: "Cabinet model not published",
        cab_model_unpublished_cap: "No listing says which cabinet this store runs. Official cab data covers Japan only, and community listings record the model just when someone noted it - so this is \"unknown\", not \"standard\".",
        offline_cab: "offline cabinet",
        offline_cabs: "offline cabinets",
        offline_cap: "This cabinet's network has shut down. It can still be played, but nothing is saved: no score history, no online play, no unlocks.",
        price_median: "{game}, median of {n} quoted prices in {country}. Not this store's own price.",
        price_sparse: "Based on only {n} listing(s) in {country}{for_game}, so treat it as a rough guide.",
        for_game: " for {game}",
        typical_country: "Typical for {country} - not this store's own price",
        permanently_closed: "Cerrado permanentemente.",
        source: "fuente",
        photo_by: "photo: {credit}",
        unknown_author: "unknown",
        listed: "listado",
        size_1: "1 to 2 cabinets",
        size_2: "3 to 9 cabinets",
        size_3: "10 to 19 cabinets",
        size_4: "20 to 49 cabinets",
        size_5: "50 or more cabinets (mega arcade)",
        size_U: "Count unknown",
      }
    },

    fr: {
      app: { title: "Arcade Maps", updated: "mis à jour {date}", data_failed: "échec du chargement des données" },
      drawer: { toggle: "Basculer les filtres", toggle_title: "Basculer le panneau de filtres" },
      meta: { updated_title: "Dernière mise à jour des données", count_title: "Marqueurs affichés / salles cartographiables" },
      search: { placeholder: "Rechercher un nom ou une adresse...", aria: "Rechercher des arcades par nom ou adresse" },
      repo: { title: "Dépôt GitHub", aria: "Dépôt GitHub" },
      tab: { filters: "Filtres", china: "Sans coordonnées" },
      pane: { games: "Jeux", cab_variants: "Variantes de borne",
        arcade_size: "Taille de l'arcade" },
      btn: { all: "tous", none: "aucun" },
      hint: {
        cab_variant: "Cocher une variante limite les marqueurs de ce jeu aux salles ayant la borne.",
        arcade_size: "Les tranches de bornes correspondent aux formes des marqueurs. Inconnu signifie qu'aucun total fiable n'a été publié.",
        china1: "Salles sans coordonnées carte (surtout Chine).",
        china2: "Issues de la liste officielle WAHLAP et de la carte communautaire BemaniCN (adresses seules). Cherchez l'adresse dans votre appli carte. Les cartes web chinoises utilisent GCJ-02 ; les points Chine tracés sont convertis en WGS-84 (approximatifs)."
      },
      nearby: {
        title: "Arcades à proximité", close: "fermer", close_aria: "Fermer la liste de proximité", pane_aria: "Arcades à proximité",
        search_area: "Chercher cette zone", empty: "Aucune salle ne correspond aux filtres. Réactivez un jeu ou une source.",
        nearest_you: "Les plus proches de votre position", nearest_to: "Les plus proches de {label}",
        showing: "Affiche les {n} salles les plus proches correspondant aux filtres. Sans coordonnées non affichées.",
        no_coords_note: "Les salles sans coordonnées ne sont pas affichées.", locate: "Afficher les arcades près de moi",
        your_location: "votre position", this_point: "ce point"
      },
      map: { aria: "Carte des arcades" },
      empty: { map: "Aucune arcade ne correspond à vos filtres" },
      foot: { data_sources: "sources de données", sources: "sources", show: "Afficher le nombre de sources", hide: "Masquer le nombre de sources" },
      lang: { button: "Langue", menu: "Choisir la langue" },
      settings: {
        title: "Paramètres", close: "Fermer les paramètres", sections: "Sections des paramètres", gear: "Paramètres",
        sec_sources: "Sources", sec_display: "Affichage", sec_location: "Localisation", sec_about: "À propos",
        sources_head: "Sources de données",
        sources_note: "Désactivez une source pour masquer ses salles. Une salle listée par plusieurs sources reste visible tant qu'une est active.",
        display_head: "Affichage",
        marker_scaling: "Taille du marqueur selon le nombre de bornes",
        marker_scaling_desc: "Les salles plus fournies sont plus grandes. Désactivez pour une taille unique (la forme indique encore le palier).",
        location_head: "Localisation",
        location_enabled: "Activer les fonctions de localisation",
        location_enabled_desc: "Affiche le bouton de localisation et la liste des arcades les plus proches.",
        location_privacy: "Votre position ne quitte jamais le navigateur.",
        location_privacy_body: " Lue uniquement sur demande, utilisée ici pour trier par distance, jamais envoyée, stockée ni partagée. Pas de serveur ni d'analytique.",
        legend: "Légende",
        icon_cabinets: "Icône : total des bornes de la salle",
        tier_unknown: "Nombre inconnu (taille moyenne)",
        cluster_note: "Groupe de 12 salles. Un liseré doré indique au moins une salle à 20+ bornes.",
        legend_note: "Chaque palier a une forme distincte. La plupart des listes officielles indiquent les jeux mais pas le nombre de bornes ; l'inconnu a une icône moyenne dédiée (\"non publié\", pas \"une borne\"). Compteurs BemaniCN et ZIv si disponibles. Tailles selon Affichage ; formes fixes.",
        icon_color: "Couleur de l'icône : jeu de la salle",
        color_note: "Une salle multi-jeux prend la couleur du premier jeu sélectionné dans l'ordre ci-dessous. La légende du dessus est un échantillon ; sur la carte, couleur du jeu de la salle.",
        badges: "Badges dans la popup de salle",
        cab_badge: "Les badges jaunes nomment la BORNE, pas le jeu : Lightning IIDX, Valkyrie/NEMSYS SOUND VOLTEX, DDR gold et Universal, GITADORA Arena, pop'n Pikapika, et builds régionaux Taiko.",
        dead_badge: "Un badge barré est une borne HORS LIGNE : maimai FiNALE et DDR pré-LCD fonctionnent encore, mais le réseau est arrêté - pas de scores, déblocages ni online.",
        badge_note: "Origine des données de borne et limites. Listes opérateurs officielles : modèles Japon seulement ; ailleurs, listes communautaires. Badge manquant = modèle non enregistré, pas \"borne standard\".",
        about_map: "À propos de cette carte",
        stats: "{stores} salles, {plottable} avec coordonnées. Données mises à jour {updated}.",
        link_source: "Code source sur GitHub", link_data: "Sources de données", link_license: "Licence MIT",
        osm_note: "Données cartographiques (c) contributeurs OpenStreetMap, ODbL. Listes de salles appartiennent à leurs sources. Coordonnées chinoises converties depuis GCJ-02 (approximatives).",
        shown: "{n} sur {total} salles cartographiables affichées avec les filtres actuels.",
        src_extra: "Source de données supplémentaire.",
        src_count_title: "salles de cette source, y compris sans coordonnées"
      },
      legend: {
        toggle: "Légende", icon_cabinets: "Icône : bornes de la salle", color_game: "Couleur : jeu",
        full: "Légende complète dans Paramètres", unknown_title: "nombre inconnu, taille moyenne"
      },
      src: {
        allnet_name: "ALL.Net", allnet_desc: "Localisateur officiel SEGA : maimai DX, CHUNITHM, O.N.G.E.K.I.",
        eagate_name: "e-amusement", eagate_desc: "Localisateur officiel KONAMI : IIDX, SOUND VOLTEX, DDR et autres Bemani.",
        wahlap_name: "WAHLAP", wahlap_desc: "Distributeur officiel SEGA en Chine continentale. Adresses seules, sans coordonnées.",
        bemanicn_name: "BemaniCN", bemanicn_desc: "Carte communautaire des bornes Bemani en Chine continentale.",
        ziv_name: "Zenius-I-Vanisher", ziv_desc: "Base de données communautaire d'arcades à couverture mondiale.",
        round1usa_name: "Round1 USA", round1usa_desc: "Liste officielle des salles Round1 aux États-Unis.",
        community_name: "Community", community_desc: "Entrées curées à la main dans ce dépôt."
      },
      place: {
        directions: "Itinéraire", nearby: "À proximité", share: "Partager", filters: "Filtres",
        close: "Fermer les détails du lieu", details: "Détails du lieu",
        address_copied: "Adresse copiée", link_copied: "Lien copié", copy_failed: "Échec de la copie",
        tap_to_copy: "Appuyer pour copier",
        listed_by: "Référencé par",
        no_map_position: "Ce salon n'a pas de position sur la carte",
        no_map_position_cap: "Seule l'adresse est publiée. Utilisez Itinéraire pour la chercher.",
        community_from: "données communautaires de {src}, peut-être obsolètes{date}",
        community_listings: "listes communautaires",
        rechecked_community: "revérifié sur {host}, toujours des données communautaires",
        checked_operator: "vérifié auprès de {host}",
        checked_operator_generic: "vérifié auprès de la page officielle de l'exploitant",
        price_common: "Prix le plus fréquent parmi les {n} machines listées ici.",
        per_machine: "Par machine, selon la liste.",
        machine_list_no_counts: "Liste de machines, sans nombre de bornes",
        machine_list_no_counts_cap: "La liste communautaire nomme les machines ci-dessous sans dire combien de chacune ; c'est un plancher, pas un inventaire.",
        cab_counts_unavailable: "Nombre de bornes indisponible",
        cab_counts_unavailable_cap: "Les sources de ce salon ne publient pas le nombre de machines.",
        approx_address: "Position d'après l'adresse",
        approx_address_cap: "La source n'a pas de coordonnées ; le pin a été géocodé depuis l'adresse imprimée.",
        approx_street: "Position d'après l'adresse (niveau rue)",
        approx_street_cap: "Géocodé à la rue, pas au bâtiment ; peut se tromper d'une ou deux portes.",
        approx_district: "Position approximative (niveau district)",
        approx_district_cap: "Sans coordonnées ; le pin est le centre du district nommé, pas le salon.",
        approx_city: "Position approximative (niveau ville)",
        approx_city_cap: "Sans coordonnées ni nom de district ; le pin est le centre de la ville.",
        back_to: "Retour à {label}",
        search_gmaps: "Rechercher dans Google Maps",
      },
      nb: {
        err_denied: "Permission de localisation refusée. Autorisez-la dans le navigateur, puis réessayez.",
        err_unavailable: "Position indisponible. Réessayez ou cherchez une ville.",
        err_timeout: "La localisation a pris trop de temps. Réessayez.",
        err_generic: "Impossible d'obtenir votre position.",
        err_empty: "Position vide. Réessayez dans un instant.",
        err_off: "La localisation est désactivée dans les paramètres.",
        err_https: "La localisation nécessite une connexion sécurisée (https).",
        err_unsupported: "Ce navigateur ne peut pas indiquer la position."
      },
      cabs: {
        sdvx_vm: "Modèle Valkyrie",
        iidx_lm: "Modèle Lightning",
        ddr_gold: "Borne dorée (20e anniv.)",
        gitadora_arena: "Modèle Arena",
        popn_pikapika: "Modèle Pikapika",
        maimai_classic: "maimai FiNALE / pre-DX",
        sdvx_nemsys: "NEMSYS (standard)",
        ddr_universal: "Universal Model (EU/NA)",
        ddr_legacy: "Borne CRT ancienne",
        other_game: "Autre",
      },
      ui: {
        shown: "{n} affichés",
        stores_total: "{n} salons au total",
        per_credit: "par crédit",
        show_more: "Voir plus",
        show_less: "Voir moins",
        search_wide: "Rechercher jeux, salles, lieux...",
        search_narrow: "Rechercher...",
        cab_model_unpublished: "Cabinet model not published",
        cab_model_unpublished_cap: "No listing says which cabinet this store runs. Official cab data covers Japan only, and community listings record the model just when someone noted it - so this is \"unknown\", not \"standard\".",
        offline_cab: "offline cabinet",
        offline_cabs: "offline cabinets",
        offline_cap: "This cabinet's network has shut down. It can still be played, but nothing is saved: no score history, no online play, no unlocks.",
        price_median: "{game}, median of {n} quoted prices in {country}. Not this store's own price.",
        price_sparse: "Based on only {n} listing(s) in {country}{for_game}, so treat it as a rough guide.",
        for_game: " for {game}",
        typical_country: "Typical for {country} - not this store's own price",
        permanently_closed: "Fermé définitivement.",
        source: "source",
        photo_by: "photo: {credit}",
        unknown_author: "unknown",
        listed: "listé",
        size_1: "1 to 2 cabinets",
        size_2: "3 to 9 cabinets",
        size_3: "10 to 19 cabinets",
        size_4: "20 to 49 cabinets",
        size_5: "50 or more cabinets (mega arcade)",
        size_U: "Count unknown",
      }
    },

    de: {
      app: { title: "Arcade Maps", updated: "aktualisiert {date}", data_failed: "Daten laden fehlgeschlagen" },
      drawer: { toggle: "Filter umschalten", toggle_title: "Filterpanel umschalten" },
      meta: { updated_title: "Daten zuletzt aktualisiert", count_title: "Angezeigte Marker / kartierbare Stores" },
      search: { placeholder: "Name oder Adresse suchen...", aria: "Arcades nach Name oder Adresse suchen" },
      repo: { title: "GitHub-Repository", aria: "GitHub-Repository" },
      tab: { filters: "Filter", china: "Ohne Koordinaten" },
      pane: { games: "Spiele", cab_variants: "Cabinett-Varianten",
        arcade_size: "Arcade-Größe" },
      btn: { all: "alle", none: "keine" },
      hint: {
        cab_variant: "Eine Variante einschränkt die Marker dieses Spiels auf Stores mit dem Cabinett.",
        arcade_size: "Cabinett-Anzahlbänder entsprechen den Markerformen. Unbekannt heißt: keine vertrauenswürdige veröffentlichte Zahl.",
        china1: "Stores ohne Kartenkoordinaten (meist China).",
        china2: "Aus der offiziellen WAHLAP-Liste und der BemaniCN-Community-Karte (nur Adressen). Adresse in der Karten-App suchen. Chinesische Webkarten nutzen GCJ-02; gezeichnete China-Punkte sind nach WGS-84 umgerechnet (ungefähr)."
      },
      nearby: {
        title: "Arcades in der Nähe", close: "schließen", close_aria: "Nähe-Liste schließen", pane_aria: "Arcades in der Nähe",
        search_area: "Diesen Bereich suchen", empty: "Keine Stores passen zu den Filtern. Spiel oder Quelle wieder aktivieren.",
        nearest_you: "Nächst zu Ihrem Standort", nearest_to: "Nächst zu {label}",
        showing: "Die {n} nächsten passenden Stores. Ohne Koordinaten werden nicht gezeigt.",
        no_coords_note: "Stores ohne Koordinaten werden nicht gezeigt.", locate: "Arcades in meiner Nähe zeigen",
        your_location: "Ihr Standort", this_point: "dieser Punkt"
      },
      map: { aria: "Arcade-Karte" },
      empty: { map: "Keine Arcades passen zu Ihren Filtern" },
      foot: { data_sources: "Datenquellen", sources: "Quellen", show: "Datenquellen-Zähler anzeigen", hide: "Datenquellen-Zähler ausblenden" },
      lang: { button: "Sprache", menu: "Sprache wählen" },
      settings: {
        title: "Einstellungen", close: "Einstellungen schließen", sections: "Einstellungsbereiche", gear: "Einstellungen",
        sec_sources: "Quellen", sec_display: "Anzeige", sec_location: "Standort", sec_about: "Info",
        sources_head: "Datenquellen",
        sources_note: "Quelle aus, um ihre Stores auszublenden. Stores in mehreren Quellen bleiben sichtbar, solange eine aktiv ist.",
        display_head: "Anzeige",
        marker_scaling: "Markergröße nach Cabinett-Anzahl",
        marker_scaling_desc: "Stores mit mehr Cabinets größer. Aus: alle Marker gleich groß (Form zeigt weiterhin die Stufe).",
        location_head: "Standort",
        location_enabled: "Standortfunktionen aktivieren",
        location_enabled_desc: "Standortbutton und Liste der nächsten Arcades anzeigen.",
        location_privacy: "Ihr Standort verlässt den Browser nie.",
        location_privacy_body: " Wird nur auf Anfrage gelesen, hier zum Sortieren nach Entfernung genutzt, nie hochgeladen, gespeichert oder geteilt. Keine Server, keine Analytics.",
        legend: "Legende",
        icon_cabinets: "Symbol: Cabinets gesamt im Store",
        tier_unknown: "Anzahl unbekannt (mittlere Größe)",
        cluster_note: "Cluster aus 12 Stores. Goldrand heißt mindestens ein 20+-Cabinett-Store darin.",
        legend_note: "Jede Stufe hat eine andere Form. Offizielle Listen nennen oft Spiele, nicht die Cabinett-Zahl; unbekannt bekommt ein eigenes mittleres Symbol (\"nicht veröffentlicht\", nicht \"ein Cabinett\"). Zahlen von BemaniCN und ZIv. Größen folgen Anzeige; Formen nicht.",
        icon_color: "Symbolfarbe: Spiel im Store",
        color_note: "Ein Store mit mehreren Spielen nimmt die Farbe des ersten gewählten Spiels in der Reihenfolge unten. Oben Beispielsfarbe; auf der Karte die Spielfarbe des Stores.",
        badges: "Badges im Store-Popup",
        cab_badge: "Gelbe Badges nennen das CABINETT, nicht das Spiel: Lightning IIDX, Valkyrie/NEMSYS SOUND VOLTEX, DDR gold & Universal, GITADORA Arena, pop'n Pikapika und regionale Taiko-Builds.",
        dead_badge: "Durchgestrichenes Badge = OFFLINE-Cabinett: maimai FiNALE und pre-LCD-DDR laufen noch, Netzwerk aus - keine Scores, Unlocks oder Online.",
        badge_note: "Herkunft der Cabinett-Daten und Grenzen. Offizielle Betreiberlisten nur Japan; sonst Community. Fehlendes Badge = Modell nicht erfasst, nicht \"Standard\".",
        about_map: "Über diese Karte",
        stats: "{stores} Stores, {plottable} mit Koordinaten. Daten aktualisiert {updated}.",
        link_source: "Quellcode auf GitHub", link_data: "Datenquellen", link_license: "MIT-Lizenz",
        osm_note: "Kartendaten (c) OpenStreetMap-Mitwirkende, ODbL. Store-Listen gehören den jeweiligen Quellen. China-Koordinaten aus GCJ-02 (ungefähr).",
        shown: "{n} von {total} kartierbaren Stores mit aktuellen Filtern angezeigt.",
        src_extra: "Zusätzliche Datenquelle.",
        src_count_title: "Stores dieser Quelle, inkl. ohne Koordinaten"
      },
      legend: {
        toggle: "Legende", icon_cabinets: "Symbol: Cabinets im Store", color_game: "Farbe: Spiel",
        full: "Volle Legende in Einstellungen", unknown_title: "Anzahl unbekannt, mittlere Größe"
      },
      src: {
        allnet_name: "ALL.Net", allnet_desc: "Offizieller SEGA-Store-Locator: maimai DX, CHUNITHM, O.N.G.E.K.I.",
        eagate_name: "e-amusement", eagate_desc: "Offizieller KONAMI-Store-Locator: IIDX, SOUND VOLTEX, DDR und andere Bemani.",
        wahlap_name: "WAHLAP", wahlap_desc: "Offizieller SEGA-Distributor Festlandchina. Nur Adressen, keine Koordinaten.",
        bemanicn_name: "BemaniCN", bemanicn_desc: "Community-Karte von Bemani-Cabinets in Festlandchina.",
        ziv_name: "Zenius-I-Vanisher", ziv_desc: "Community-Arcade-Datenbank mit weltweiter Abdeckung.",
        round1usa_name: "Round1 USA", round1usa_desc: "Offizielle Round1-Venue-Liste für die USA.",
        community_name: "Community", community_desc: "Manuell kuratierte Einträge in diesem Repository."
      },
      place: {
        directions: "Route", nearby: "In der Nähe", share: "Teilen", filters: "Filter",
        close: "Ortsdetails schließen", details: "Ortsdetails",
        address_copied: "Adresse kopiert", link_copied: "Link kopiert", copy_failed: "Kopieren fehlgeschlagen",
        tap_to_copy: "Tippen zum Kopieren",
        listed_by: "Gelistet von",
        no_map_position: "Dieser Laden hat keine Kartenposition",
        no_map_position_cap: "Nur die Adresse ist veröffentlicht. Nutze Route zum Suchen.",
        community_from: "Community-Daten von {src}, möglicherweise veraltet{date}",
        community_listings: "Community-Listen",
        rechecked_community: "auf {host} erneut geprüft, weiterhin Community-Daten",
        checked_operator: "geprüft gegen {host}",
        checked_operator_generic: "geprüft gegen die offizielle Betreiberseite",
        price_common: "Häufigster Preis unter den {n} hier gelisteten Automaten.",
        per_machine: "Pro Automat, wie gelistet.",
        machine_list_no_counts: "Automatenliste, aber keine Stückzahlen",
        machine_list_no_counts_cap: "Die Community-Liste nennt die Automaten unten, ohne wie viele von jedem; das ist eine Untergrenze, keine Inventur.",
        cab_counts_unavailable: "Stückzahlen nicht verfügbar",
        cab_counts_unavailable_cap: "Die Quellen dieses Ladens veröffentlichen keine Automatenanzahl.",
        approx_address: "Position aus der Adresse",
        approx_address_cap: "Quelle ohne Koordinaten; Pin aus der gedruckten Adresse geocodiert.",
        approx_street: "Position aus der Adresse (Straßenebene)",
        approx_street_cap: "Auf die Straße geocodiert, nicht das Gebäude; kann ein, zwei Türen daneben liegen.",
        approx_district: "Ungefähre Position (Bezirksebene)",
        approx_district_cap: "Ohne Koordinaten; Pin ist der Bezirksmittelpunkt der Adresse, nicht der Laden.",
        approx_city: "Ungefähre Position (Stadtebene)",
        approx_city_cap: "Ohne Koordinaten und ohne Bezirksnamen; Pin ist der Stadtmitte.",
        back_to: "Zurück zu {label}",
        search_gmaps: "In Google Maps suchen",
      },
      nb: {
        err_denied: "Standortberechtigung verweigert. In den Browser-Einstellungen erlauben und erneut versuchen.",
        err_unavailable: "Standort derzeit nicht verfügbar. Erneut versuchen oder Stadt suchen.",
        err_timeout: "Standortabfrage zu langsam. Erneut versuchen.",
        err_generic: "Standort konnte nicht ermittelt werden.",
        err_empty: "Standort war leer. Gleich erneut versuchen.",
        err_off: "Standort ist in den Einstellungen aus.",
        err_https: "Standort braucht eine sichere (https) Verbindung.",
        err_unsupported: "Dieser Browser kann den Standort nicht melden."
      },
      cabs: {
        sdvx_vm: "Valkyrie-Modell",
        iidx_lm: "Lightning-Modell",
        ddr_gold: "Gold-Cab (20. Jubiläum)",
        gitadora_arena: "Arena-Modell",
        popn_pikapika: "Pikapika-Modell",
        maimai_classic: "maimai FiNALE / pre-DX",
        sdvx_nemsys: "NEMSYS (Standard)",
        ddr_universal: "Universal Model (EU/NA)",
        ddr_legacy: "Legacy-CRT-Gehäuse",
        other_game: "Sonstige",
      },
      ui: {
        shown: "{n} angezeigt",
        stores_total: "{n} Läden gesamt",
        per_credit: "pro Credit",
        show_more: "Mehr anzeigen",
        show_less: "Weniger anzeigen",
        search_wide: "Spiele, Arcades, Orte suchen...",
        search_narrow: "Suchen...",
        cab_model_unpublished: "Cabinet model not published",
        cab_model_unpublished_cap: "No listing says which cabinet this store runs. Official cab data covers Japan only, and community listings record the model just when someone noted it - so this is \"unknown\", not \"standard\".",
        offline_cab: "offline cabinet",
        offline_cabs: "offline cabinets",
        offline_cap: "This cabinet's network has shut down. It can still be played, but nothing is saved: no score history, no online play, no unlocks.",
        price_median: "{game}, median of {n} quoted prices in {country}. Not this store's own price.",
        price_sparse: "Based on only {n} listing(s) in {country}{for_game}, so treat it as a rough guide.",
        for_game: " for {game}",
        typical_country: "Typical for {country} - not this store's own price",
        permanently_closed: "Dauerhaft geschlossen.",
        source: "Quelle",
        photo_by: "photo: {credit}",
        unknown_author: "unknown",
        listed: "gelistet",
        size_1: "1 to 2 cabinets",
        size_2: "3 to 9 cabinets",
        size_3: "10 to 19 cabinets",
        size_4: "20 to 49 cabinets",
        size_5: "50 or more cabinets (mega arcade)",
        size_U: "Count unknown",
      }
    },

    pt: {
      app: { title: "Arcade Maps", updated: "atualizado {date}", data_failed: "falha ao carregar dados" },
      drawer: { toggle: "Alternar filtros", toggle_title: "Alternar painel de filtros" },
      meta: { updated_title: "Dados atualizados pela última vez", count_title: "Marcadores exibidos / lojas no mapa" },
      search: { placeholder: "Buscar nome ou endereço...", aria: "Buscar arcades por nome ou endereço" },
      repo: { title: "Repositório GitHub", aria: "Repositório GitHub" },
      tab: { filters: "Filtros", china: "Sem coordenadas" },
      pane: { games: "Jogos", cab_variants: "Variantes de cabine",
        arcade_size: "Tamanho do arcade" },
      btn: { all: "todos", none: "nenhum" },
      hint: {
        cab_variant: "Marcar uma variante limita os marcadores desse jogo às lojas com a cabine.",
        arcade_size: "Faixas de cabines coincidem com as formas dos marcadores. Desconhecido significa que nenhum total confiável foi publicado.",
        china1: "Lojas sem coordenadas no mapa (principalmente China).",
        china2: "Da lista oficial WAHLAP e do mapa comunitário BemaniCN (só endereços). Busque o endereço no app de mapas. Mapas web chineses usam GCJ-02; pontos da China no mapa foram convertidos para WGS-84 (aproximados)."
      },
      nearby: {
        title: "Arcades próximos", close: "fechar", close_aria: "Fechar lista próxima", pane_aria: "Arcades próximos",
        search_area: "Buscar esta área", empty: "Nenhuma loja corresponde aos filtros. Reative um jogo ou uma fonte.",
        nearest_you: "Mais próximos da sua localização", nearest_to: "Mais próximos de {label}",
        showing: "Mostrando as {n} lojas mais próximas que correspondem. Sem coordenadas não aparecem.",
        no_coords_note: "Lojas sem coordenadas não são mostradas.", locate: "Mostrar arcades perto de mim",
        your_location: "sua localização", this_point: "este ponto"
      },
      map: { aria: "Mapa de arcades" },
      empty: { map: "Nenhum arcade corresponde aos seus filtros" },
      foot: { data_sources: "fontes de dados", sources: "fontes", show: "Mostrar contagens de fontes", hide: "Ocultar contagens de fontes" },
      lang: { button: "Idioma", menu: "Escolher idioma" },
      settings: {
        title: "Configurações", close: "Fechar configurações", sections: "Seções de configurações", gear: "Configurações",
        sec_sources: "Fontes", sec_display: "Exibição", sec_location: "Localização", sec_about: "Sobre",
        sources_head: "Fontes de dados",
        sources_note: "Desative uma fonte para ocultar suas lojas. Loja em várias fontes permanece se alguma estiver ativa.",
        display_head: "Exibição",
        marker_scaling: "Tamanho do marcador pelo número de cabines",
        marker_scaling_desc: "Lojas com mais cabines ficam maiores. Desative para o mesmo tamanho em todos (a forma ainda mostra o nível).",
        location_head: "Localização",
        location_enabled: "Ativar recursos de localização",
        location_enabled_desc: "Mostra o botão de localização e a lista de arcades mais próximos.",
        location_privacy: "Sua localização nunca sai do navegador.",
        location_privacy_body: " Lida só quando você pede, usada nesta página para ordenar por distância, e nunca enviada, armazenada ou compartilhada. Sem servidor e sem analytics.",
        legend: "Legenda",
        icon_cabinets: "Ícone: total de cabines na loja",
        tier_unknown: "Contagem desconhecida (tamanho médio)",
        cluster_note: "Cluster de 12 lojas. Borda dourada significa ao menos uma loja com 20+ cabines dentro.",
        legend_note: "Cada nível tem forma diferente. A maioria das listas oficiais publica jogos, não o número de cabines; desconhecido ganha ícone médio próprio (\"não publicado\", não \"uma cabine\"). Contagens de BemaniCN e ZIv. Tamanhos seguem Exibição; formas não.",
        icon_color: "Cor do ícone: jogo na loja",
        color_note: "Loja com vários jogos pega a cor do primeiro jogo selecionado na ordem abaixo. Legenda acima usa cor de amostra; no mapa, a do jogo da loja.",
        badges: "Emblemas no popup da loja",
        cab_badge: "Emblemas amarelos nomeiam a CABINE, não o jogo: Lightning IIDX, Valkyrie/NEMSYS SOUND VOLTEX, DDR gold e Universal, GITADORA Arena, pop'n Pikapika e builds regionais de Taiko.",
        dead_badge: "Emblema riscado é cabine OFFLINE: maimai FiNALE e DDR pré-LCD ainda rodam, mas a rede encerrou - sem scores, desbloqueios ou online.",
        badge_note: "Origem dos dados de cabine e limites. Listas oficiais publicam modelos só no Japão; fora, listas da comunidade. Emblema ausente = modelo não registrado, não \"cabine padrão\".",
        about_map: "Sobre este mapa",
        stats: "{stores} lojas, {plottable} com coordenadas. Dados atualizados {updated}.",
        link_source: "Código-fonte no GitHub", link_data: "Fontes de dados", link_license: "Licença MIT",
        osm_note: "Dados do mapa (c) contribuidores OpenStreetMap, ODbL. Listagens pertencem às fontes. Coordenadas da China convertidas de GCJ-02 (aproximadas).",
        shown: "{n} de {total} lojas mapeáveis com os filtros atuais.",
        src_extra: "Fonte de dados adicional.",
        src_count_title: "lojas desta fonte, incluindo sem coordenadas"
      },
      legend: {
        toggle: "Legenda", icon_cabinets: "Ícone: cabines na loja", color_game: "Cor: jogo",
        full: "Legenda completa em Configurações", unknown_title: "contagem desconhecida, tamanho médio"
      },
      src: {
        allnet_name: "ALL.Net", allnet_desc: "Localizador oficial SEGA: maimai DX, CHUNITHM, O.N.G.E.K.I.",
        eagate_name: "e-amusement", eagate_desc: "Localizador oficial KONAMI: IIDX, SOUND VOLTEX, DDR e outros Bemani.",
        wahlap_name: "WAHLAP", wahlap_desc: "Distribuidor oficial SEGA na China continental. Só endereços, sem coordenadas.",
        bemanicn_name: "BemaniCN", bemanicn_desc: "Mapa comunitário de cabines Bemani na China continental.",
        ziv_name: "Zenius-I-Vanisher", ziv_desc: "Banco de dados comunitário de arcades com cobertura mundial.",
        round1usa_name: "Round1 USA", round1usa_desc: "Lista oficial de venues Round1 nos Estados Unidos.",
        community_name: "Community", community_desc: "Entradas curadas à mão neste repositório."
      },
      place: {
        directions: "Direções", nearby: "Próximos", share: "Compartilhar", filters: "Filtros",
        close: "Fechar detalhes do local", details: "Detalhes do local",
        address_copied: "Endereço copiado", link_copied: "Link copiado", copy_failed: "Falha ao copiar",
        tap_to_copy: "Toque para copiar",
        listed_by: "Listado por",
        no_map_position: "Esta loja não tem posição no mapa",
        no_map_position_cap: "Só o endereço foi publicado. Use Direções para pesquisar.",
        community_from: "dados da comunidade de {src}; podem estar desatualizados{date}",
        community_listings: "listagens da comunidade",
        rechecked_community: "reconferido em {host}; ainda são dados da comunidade",
        checked_operator: "conferido com {host}",
        checked_operator_generic: "conferido com a página oficial do operador",
        price_common: "Preço mais comum entre as {n} máquinas listadas aqui.",
        per_machine: "Por máquina, conforme a lista.",
        machine_list_no_counts: "Há lista de máquinas, sem contagem de cabines",
        machine_list_no_counts_cap: "A lista da comunidade nomeia as máquinas abaixo sem dizer quantas de cada; é um piso, não um inventário.",
        cab_counts_unavailable: "Contagem de cabines indisponível",
        cab_counts_unavailable_cap: "As fontes desta loja não publicam quantas máquinas ela tem.",
        approx_address: "Posição a partir do endereço",
        approx_address_cap: "A fonte não tem coordenadas; o pino foi geocodificado do endereço impresso.",
        approx_street: "Posição a partir do endereço (nível rua)",
        approx_street_cap: "Geocodificado para a rua, não o prédio; pode errar uma ou duas portas.",
        approx_district: "Posição aproximada (nível distrito)",
        approx_district_cap: "Sem coordenadas; o pino é o centro do distrito do endereço, não a loja.",
        approx_city: "Posição aproximada (nível cidade)",
        approx_city_cap: "Sem coordenadas e sem nome de distrito; o pino é o centro da cidade.",
        back_to: "Voltar para {label}",
        search_gmaps: "Pesquisar no Google Maps",
      },
      nb: {
        err_denied: "Permissão de localização negada. Permita no navegador e tente de novo.",
        err_unavailable: "Localização indisponível. Tente de novo ou busque uma cidade.",
        err_timeout: "A localização demorou demais. Tente de novo.",
        err_generic: "Não foi possível obter sua localização.",
        err_empty: "Localização veio vazia. Tente de novo em instantes.",
        err_off: "Localização desligada nas configurações.",
        err_https: "Localização precisa de conexão segura (https).",
        err_unsupported: "Este navegador não pode informar a localização."
      },
      cabs: {
        sdvx_vm: "Modelo Valkyrie",
        iidx_lm: "Modelo Lightning",
        ddr_gold: "Cabine dourada (20º aniv.)",
        gitadora_arena: "Modelo Arena",
        popn_pikapika: "Modelo Pikapika",
        maimai_classic: "maimai FiNALE / pre-DX",
        sdvx_nemsys: "NEMSYS (padrão)",
        ddr_universal: "Universal Model (EU/NA)",
        ddr_legacy: "Cabine CRT antiga",
        other_game: "Outros",
      },
      ui: {
        shown: "{n} exibidos",
        stores_total: "{n} lojas no total",
        per_credit: "por crédito",
        show_more: "Mostrar mais",
        show_less: "Mostrar menos",
        search_wide: "Buscar jogos, arcades, lugares...",
        search_narrow: "Buscar...",
        cab_model_unpublished: "Cabinet model not published",
        cab_model_unpublished_cap: "No listing says which cabinet this store runs. Official cab data covers Japan only, and community listings record the model just when someone noted it - so this is \"unknown\", not \"standard\".",
        offline_cab: "offline cabinet",
        offline_cabs: "offline cabinets",
        offline_cap: "This cabinet's network has shut down. It can still be played, but nothing is saved: no score history, no online play, no unlocks.",
        price_median: "{game}, median of {n} quoted prices in {country}. Not this store's own price.",
        price_sparse: "Based on only {n} listing(s) in {country}{for_game}, so treat it as a rough guide.",
        for_game: " for {game}",
        typical_country: "Typical for {country} - not this store's own price",
        permanently_closed: "Fechado permanentemente.",
        source: "fonte",
        photo_by: "photo: {credit}",
        unknown_author: "unknown",
        size_1: "1 to 2 cabinets",
        size_2: "3 to 9 cabinets",
        size_3: "10 to 19 cabinets",
        size_4: "20 to 49 cabinets",
        size_5: "50 or more cabinets (mega arcade)",
        size_U: "Count unknown",
      }
    },

    it: {
      app: { title: "Arcade Maps", updated: "aggiornato {date}", data_failed: "caricamento dati non riuscito" },
      drawer: { toggle: "Attiva/disattiva filtri", toggle_title: "Attiva/disattiva pannello filtri" },
      meta: { updated_title: "Dati aggiornati l'ultima volta", count_title: "Marcatori mostrati / negozi mappabili" },
      search: { placeholder: "Cerca nome o indirizzo...", aria: "Cerca arcade per nome o indirizzo" },
      repo: { title: "Repository GitHub", aria: "Repository GitHub" },
      tab: { filters: "Filtri", china: "Senza coordinate" },
      pane: { games: "Giochi", cab_variants: "Varianti cabinato",
        arcade_size: "Dimensione arcade" },
      btn: { all: "tutti", none: "nessuno" },
      hint: {
        cab_variant: "Selezionare una variante limita i marcatori di quel gioco ai negozi con quel cabinato.",
        arcade_size: "Le fasce di cabinati corrispondono alle forme dei marker. Sconosciuto significa che non è stato pubblicato un conteggio affidabile.",
        china1: "Negozi senza coordinate sulla mappa (soprattutto Cina).",
        china2: "Dalla lista ufficiale WAHLAP e dalla mappa community BemaniCN (solo indirizzi). Cerca l'indirizzo nell'app mappe. Le mappe web cinesi usano GCJ-02; i punti Cina tracciati sono convertiti in WGS-84 (approssimativi)."
      },
      nearby: {
        title: "Arcade vicini", close: "chiudi", close_aria: "Chiudi elenco vicini", pane_aria: "Arcade vicini",
        search_area: "Cerca quest'area", empty: "Nessun negozio corrisponde ai filtri. Riattiva un gioco o una fonte.",
        nearest_you: "Più vicini alla tua posizione", nearest_to: "Più vicini a {label}",
        showing: "Mostra i {n} negozi più vicini che corrispondono. Senza coordinate non mostrati.",
        no_coords_note: "I negozi senza coordinate non sono mostrati.", locate: "Mostra arcade vicino a me",
        your_location: "la tua posizione", this_point: "questo punto"
      },
      map: { aria: "Mappa arcade" },
      empty: { map: "Nessun arcade corrisponde ai filtri" },
      foot: { data_sources: "fonti dati", sources: "fonti", show: "Mostra conteggi fonti dati", hide: "Nascondi conteggi fonti dati" },
      lang: { button: "Lingua", menu: "Scegli lingua" },
      settings: {
        title: "Impostazioni", close: "Chiudi impostazioni", sections: "Sezioni impostazioni", gear: "Impostazioni",
        sec_sources: "Fonti", sec_display: "Visualizzazione", sec_location: "Posizione", sec_about: "Informazioni",
        sources_head: "Fonti dati",
        sources_note: "Disattiva una fonte per nasconderne i negozi. Un negozio in più fonti resta se una è attiva.",
        display_head: "Visualizzazione",
        marker_scaling: "Dimensione marker per numero di cabinati",
        marker_scaling_desc: "Negozi più affollati più grandi. Disattiva per stessa dimensione (la forma indica ancora il livello).",
        location_head: "Posizione",
        location_enabled: "Abilita funzioni di posizione",
        location_enabled_desc: "Mostra il pulsante di localizzazione e l'elenco degli arcade più vicini.",
        location_privacy: "La tua posizione non lascia mai il browser.",
        location_privacy_body: " Letta solo su richiesta, usata qui per ordinare per distanza, mai caricata, salvata o condivisa. Nessun server né analytics.",
        legend: "Legenda",
        icon_cabinets: "Icona: cabinati totali nel negozio",
        tier_unknown: "Conteggio sconosciuto (dimensione media)",
        cluster_note: "Cluster di 12 negozi. Bordo oro: almeno un negozio con 20+ cabinati dentro.",
        legend_note: "Ogni livello ha una forma diversa. La maggior parte delle liste ufficiali pubblica i giochi ma non il numero di cabinati; lo sconosciuto ha un'icona media dedicata (\"non pubblicato\", non \"un cabinato\"). Conteggi da BemaniCN e ZIv. Dimensioni seguono Visualizzazione; forme fisse.",
        icon_color: "Colore icona: gioco del negozio",
        color_note: "Un negozio con più giochi prende il colore del primo gioco selezionato nell'ordine sotto. La legenda sopra usa un colore campione; sulla mappa quello del gioco del negozio.",
        badges: "Badge nel popup del negozio",
        cab_badge: "I badge gialli nominano il CABINATO, non il gioco: Lightning IIDX, Valkyrie/NEMSYS SOUND VOLTEX, DDR gold e Universal, GITADORA Arena, pop'n Pikapika e build regionali Taiko.",
        dead_badge: "Badge barrato = cabinato OFFLINE: maimai FiNALE e DDR pre-LCD funzionano ancora, ma le reti sono chiuse - niente punteggi, sblocchi o online.",
        badge_note: "Origine dei dati cabinato e limiti. Liste operatori ufficiali solo Giappone; altrove liste community. Badge assente = modello non registrato, non \"cabinato standard\".",
        about_map: "Informazioni su questa mappa",
        stats: "{stores} negozi, {plottable} con coordinate. Dati aggiornati {updated}.",
        link_source: "Codice sorgente su GitHub", link_data: "Fonti dati", link_license: "Licenza MIT",
        osm_note: "Dati mappa (c) contributori OpenStreetMap, ODbL. Gli elenchi appartengono alle rispettive fonti. Coordinate Cina convertite da GCJ-02 (approssimative).",
        shown: "{n} di {total} negozi mappabili con i filtri attuali.",
        src_extra: "Fonte dati aggiuntiva.",
        src_count_title: "negozi di questa fonte, inclusi senza coordinate"
      },
      legend: {
        toggle: "Legenda", icon_cabinets: "Icona: cabinati nel negozio", color_game: "Colore: gioco",
        full: "Legenda completa in Impostazioni", unknown_title: "conteggio sconosciuto, dimensione media"
      },
      src: {
        allnet_name: "ALL.Net", allnet_desc: "Locator ufficiale SEGA: maimai DX, CHUNITHM, O.N.G.E.K.I.",
        eagate_name: "e-amusement", eagate_desc: "Locator ufficiale KONAMI: IIDX, SOUND VOLTEX, DDR e altri Bemani.",
        wahlap_name: "WAHLAP", wahlap_desc: "Distributore ufficiale SEGA Cina continentale. Solo indirizzi, senza coordinate.",
        bemanicn_name: "BemaniCN", bemanicn_desc: "Mappa community di cabinati Bemani in Cina continentale.",
        ziv_name: "Zenius-I-Vanisher", ziv_desc: "Database community di arcade a copertura mondiale.",
        round1usa_name: "Round1 USA", round1usa_desc: "Elenco ufficiale venue Round1 negli Stati Uniti.",
        community_name: "Community", community_desc: "Voci curate a mano in questo repository."
      },
      place: {
        directions: "Indicazioni", nearby: "Vicini", share: "Condividi", filters: "Filtri",
        close: "Chiudi dettagli luogo", details: "Dettagli luogo",
        address_copied: "Indirizzo copiato", link_copied: "Link copiato", copy_failed: "Copia non riuscita",
        tap_to_copy: "Tocca per copiare",
        listed_by: "Elencato da",
        no_map_position: "Questo locale non ha posizione sulla mappa",
        no_map_position_cap: "È pubblicato solo l'indirizzo. Usa Indicazioni per cercarlo.",
        community_from: "dati della community da {src}; potrebbero non essere aggiornati{date}",
        community_listings: "elenchi della community",
        rechecked_community: "ricontrollato su {host}; restano dati della community",
        checked_operator: "verificato su {host}",
        checked_operator_generic: "verificato sulla pagina ufficiale dell'operatore",
        price_common: "Prezzo più comune tra le {n} macchine elencate qui.",
        per_machine: "Per macchina, come da elenco.",
        machine_list_no_counts: "Elenco macchine senza numero di cabinati",
        machine_list_no_counts_cap: "L'elenco community nomina le macchine sotto senza dire quante di ciascuna; è un minimo, non un inventario.",
        cab_counts_unavailable: "Numero di cabinati non disponibile",
        cab_counts_unavailable_cap: "Le fonti di questo locale non pubblicano quante macchine ha.",
        approx_address: "Posizione dall'indirizzo",
        approx_address_cap: "La fonte non ha coordinate; il pin è geocodificato dall'indirizzo stampato.",
        approx_street: "Posizione dall'indirizzo (livello strada)",
        approx_street_cap: "Geocodificato sulla strada, non sull'edificio; può sbagliare di una-due porte.",
        approx_district: "Posizione approssimativa (livello distretto)",
        approx_district_cap: "Senza coordinate; il pin è il centro del distretto nell'indirizzo, non il locale.",
        approx_city: "Posizione approssimativa (livello città)",
        approx_city_cap: "Senza coordinate né nome di distretto; il pin è il centro della città.",
        back_to: "Torna a {label}",
        search_gmaps: "Cerca su Google Maps",
      },
      nb: {
        err_denied: "Permesso di posizione negato. Consentilo nelle impostazioni del browser e riprova.",
        err_unavailable: "Posizione non disponibile. Riprova o cerca una città.",
        err_timeout: "La posizione ha impiegato troppo. Riprova.",
        err_generic: "Impossibile ottenere la tua posizione.",
        err_empty: "Posizione vuota. Riprova tra poco.",
        err_off: "Posizione disattivata nelle impostazioni.",
        err_https: "La posizione richiede una connessione sicura (https).",
        err_unsupported: "Questo browser non può segnalare la posizione."
      },
      cabs: {
        sdvx_vm: "Modello Valkyrie",
        iidx_lm: "Modello Lightning",
        ddr_gold: "Cabinato oro (20º anniv.)",
        gitadora_arena: "Modello Arena",
        popn_pikapika: "Modello Pikapika",
        maimai_classic: "maimai FiNALE / pre-DX",
        sdvx_nemsys: "NEMSYS (standard)",
        ddr_universal: "Universal Model (EU/NA)",
        ddr_legacy: "Cabinato CRT legacy",
        other_game: "Altro",
      },
      ui: {
        shown: "{n} mostrati",
        stores_total: "{n} locali in totale",
        per_credit: "per credito",
        show_more: "Mostra di più",
        show_less: "Mostra meno",
        search_wide: "Cerca giochi, sale, luoghi...",
        search_narrow: "Cerca...",
        cab_model_unpublished: "Cabinet model not published",
        cab_model_unpublished_cap: "No listing says which cabinet this store runs. Official cab data covers Japan only, and community listings record the model just when someone noted it - so this is \"unknown\", not \"standard\".",
        offline_cab: "offline cabinet",
        offline_cabs: "offline cabinets",
        offline_cap: "This cabinet's network has shut down. It can still be played, but nothing is saved: no score history, no online play, no unlocks.",
        price_median: "{game}, median of {n} quoted prices in {country}. Not this store's own price.",
        price_sparse: "Based on only {n} listing(s) in {country}{for_game}, so treat it as a rough guide.",
        for_game: " for {game}",
        typical_country: "Typical for {country} - not this store's own price",
        permanently_closed: "Chiuso definitivamente.",
        source: "fonte",
        photo_by: "photo: {credit}",
        unknown_author: "unknown",
        size_1: "1 to 2 cabinets",
        size_2: "3 to 9 cabinets",
        size_3: "10 to 19 cabinets",
        size_4: "20 to 49 cabinets",
        size_5: "50 or more cabinets (mega arcade)",
        size_U: "Count unknown",
      }
    },

    ru: {
      app: { title: "Arcade Maps", updated: "обновлено {date}", data_failed: "не удалось загрузить данные" },
      drawer: { toggle: "Переключить фильтры", toggle_title: "Переключить панель фильтров" },
      meta: { updated_title: "Данные обновлены", count_title: "Показанные маркеры / точки на карте" },
      search: { placeholder: "Поиск по названию или адресу...", aria: "Поиск аркад по названию или адресу" },
      repo: { title: "Репозиторий GitHub", aria: "Репозиторий GitHub" },
      tab: { filters: "Фильтры", china: "Без координат" },
      pane: { games: "Игры", cab_variants: "Варианты кабинетов",
        arcade_size: "Размер аркады" },
      btn: { all: "все", none: "нет" },
      hint: {
        cab_variant: "Выбор варианта ограничивает маркеры этой игры залами с таким кабинетом.",
        arcade_size: "Диапазоны числа кабинетов совпадают с формами маркеров. Неизвестно значит, что надёжного опубликованного числа нет.",
        china1: "Залы без координат на карте (в основном Китай).",
        china2: "Из официального списка WAHLAP и карты сообщества BemaniCN (только адреса). Ищите адрес в приложении карт. Китайские веб-карты используют GCJ-02; точки Китая на карте переведены в WGS-84 (приблизительно)."
      },
      nearby: {
        title: "Аркады рядом", close: "закрыть", close_aria: "Закрыть список рядом", pane_aria: "Аркады рядом",
        search_area: "Искать эту область", empty: "Нет залов по текущим фильтрам. Включите игру или источник снова.",
        nearest_you: "Ближайшие к вам", nearest_to: "Ближайшие к {label}",
        showing: "Показаны {n} ближайших залов по фильтрам. Без координат не показываются.",
        no_coords_note: "Залы без координат не показываются.", locate: "Показать аркады рядом со мной",
        your_location: "ваше местоположение", this_point: "эта точка"
      },
      map: { aria: "Карта аркад" },
      empty: { map: "Нет аркад по вашим фильтрам" },
      foot: { data_sources: "источники данных", sources: "источники", show: "Показать число источников", hide: "Скрыть число источников" },
      lang: { button: "Язык", menu: "Выбрать язык" },
      settings: {
        title: "Настройки", close: "Закрыть настройки", sections: "Разделы настроек", gear: "Настройки",
        sec_sources: "Источники", sec_display: "Отображение", sec_location: "Геолокация", sec_about: "О карте",
        sources_head: "Источники данных",
        sources_note: "Отключите источник, чтобы скрыть его залы. Зал из нескольких источников виден, пока включён хоть один.",
        display_head: "Отображение",
        marker_scaling: "Размер маркера по числу кабинетов",
        marker_scaling_desc: "Залы с большим числом кабинетов крупнее. Выключите, чтобы все маркеры были одного размера (форма по-прежнему показывает уровень).",
        location_head: "Геолокация",
        location_enabled: "Включить функции геолокации",
        location_enabled_desc: "Показать кнопку геолокации и список ближайших аркад.",
        location_privacy: "Ваше местоположение не покидает браузер.",
        location_privacy_body: " Читается только по запросу, используется на этой странице для сортировки по расстоянию и никогда не загружается, не хранится и не передаётся. Нет сервера и аналитики.",
        legend: "Легенда",
        icon_cabinets: "Значок: всего кабинетов в зале",
        tier_unknown: "Число неизвестно (средний размер)",
        cluster_note: "Кластер из 12 залов. Золотая обводка значит, что внутри есть зал с 20+ кабинетами.",
        legend_note: "У каждого уровня своя форма. Официальные списки чаще указывают игры, но не число кабинетов; неизвестное получает отдельный средний значок (\"не опубликовано\", не \"один кабинет\"). Числа из BemaniCN и ZIv. Размеры по настройке отображения; формы фиксированы.",
        icon_color: "Цвет значка: игра в зале",
        color_note: "Зал с несколькими играми берёт цвет первой выбранной игры в порядке ниже. В легенде выше образец; на карте цвет игры зала.",
        badges: "Значки во всплывающем окне зала",
        cab_badge: "Жёлтые значки называют КАБИНЕТ, не игру: Lightning IIDX, Valkyrie/NEMSYS SOUND VOLTEX, DDR gold и Universal, GITADORA Arena, pop'n Pikapika и региональные сборки Taiko.",
        dead_badge: "Зачёркнутый значок - ОФФЛАЙН-кабинет: maimai FiNALE и DDR до LCD ещё работают, но сеть закрыта - без очков, разблокировок и онлайна.",
        badge_note: "Откуда данные о кабинетах и их пределы. Официальные списки моделей - только Япония; иначе - списки сообщества. Нет значка = модель не записана, не \"стандартный кабинет\".",
        about_map: "Об этой карте",
        stats: "{stores} залов, {plottable} с координатами. Данные обновлены {updated}.",
        link_source: "Исходный код на GitHub", link_data: "Источники данных", link_license: "Лицензия MIT",
        osm_note: "Данные карты (c) участники OpenStreetMap, ODbL. Списки залов принадлежат источникам. Координаты Китая переведены из GCJ-02 (приблизительно).",
        shown: "{n} из {total} залов на карте с текущими фильтрами.",
        src_extra: "Дополнительный источник данных.",
        src_count_title: "залы этого источника, включая без координат"
      },
      legend: {
        toggle: "Легенда", icon_cabinets: "Значок: кабинеты в зале", color_game: "Цвет: игра",
        full: "Полная легенда в Настройках", unknown_title: "число неизвестно, средний размер"
      },
      src: {
        allnet_name: "ALL.Net", allnet_desc: "Официальный локатор SEGA: maimai DX, CHUNITHM, O.N.G.E.K.I.",
        eagate_name: "e-amusement", eagate_desc: "Официальный локатор KONAMI: IIDX, SOUND VOLTEX, DDR и другие Bemani.",
        wahlap_name: "WAHLAP", wahlap_desc: "Официальный дистрибьютор SEGA в материковом Китае. Только адреса, без координат.",
        bemanicn_name: "BemaniCN", bemanicn_desc: "Карта сообщества кабинетов Bemani в материковом Китае.",
        ziv_name: "Zenius-I-Vanisher", ziv_desc: "Сообщественная база аркад с мировым охватом.",
        round1usa_name: "Round1 USA", round1usa_desc: "Официальный список площадок Round1 в США.",
        community_name: "Community", community_desc: "Записи, собранные вручную в этом репозитории."
      },
      place: {
        directions: "Маршрут", nearby: "Рядом", share: "Поделиться", filters: "Фильтры",
        close: "Закрыть сведения о месте", details: "Сведения о месте",
        address_copied: "Адрес скопирован", link_copied: "Ссылка скопирована", copy_failed: "Не удалось скопировать",
        tap_to_copy: "Нажмите, чтобы скопировать",
        listed_by: "Указано в",
        no_map_position: "У этой точки нет позиции на карте",
        no_map_position_cap: "Опубликован только адрес. Используйте «Маршрут», чтобы найти.",
        community_from: "сообщество {src}, данные могут устареть{date}",
        community_listings: "сообщества",
        rechecked_community: "перепроверено на {host}, всё ещё данные сообщества",
        checked_operator: "сверено с {host}",
        checked_operator_generic: "сверено с официальной страницей оператора",
        price_common: "Самая частая цена среди {n} автоматов в списке здесь.",
        per_machine: "За автомат, как в списке.",
        machine_list_no_counts: "Есть список автоматов, без количества кабинетов",
        machine_list_no_counts_cap: "Список сообщества называет автоматы ниже, не указывая сколько каждого; это нижняя граница, а не инвентаризация.",
        cab_counts_unavailable: "Количество кабинетов недоступно",
        cab_counts_unavailable_cap: "Источники этой точки не публикуют число автоматов.",
        approx_address: "Позиция по адресу",
        approx_address_cap: "В источнике нет координат; пин геокодирован по напечатанному адресу.",
        approx_street: "Позиция по адресу (уровень улицы)",
        approx_street_cap: "Геокодировано до улицы, не до здания; может ошибиться на одну-две двери.",
        approx_district: "Приблизительная позиция (район)",
        approx_district_cap: "Без координат; пин — центр района из адреса, не сам зал.",
        approx_city: "Приблизительная позиция (город)",
        approx_city_cap: "Без координат и без названия района; пин — центр города.",
        back_to: "Назад к {label}",
        search_gmaps: "Искать в Google Картах",
      },
      nb: {
        err_denied: "Доступ к геолокации запрещён. Разрешите в настройках браузера и повторите.",
        err_unavailable: "Местоположение недоступно. Повторите или найдите город.",
        err_timeout: "Получение позиции заняло слишком долго. Повторите.",
        err_generic: "Не удалось получить ваше местоположение.",
        err_empty: "Местоположение пустое. Повторите чуть позже.",
        err_off: "Геолокация выключена в настройках.",
        err_https: "Для геолокации нужно защищённое (https) соединение.",
        err_unsupported: "Этот браузер не может сообщить местоположение."
      },
      cabs: {
        sdvx_vm: "Valkyrie-модель",
        iidx_lm: "Lightning-модель",
        ddr_gold: "Золотой cab (20 лет)",
        gitadora_arena: "Arena-модель",
        popn_pikapika: "Pikapika-модель",
        maimai_classic: "maimai FiNALE / pre-DX",
        sdvx_nemsys: "NEMSYS (стандарт)",
        ddr_universal: "Universal Model (EU/NA)",
        ddr_legacy: "Legacy CRT-кабинет",
        other_game: "Прочее",
      },
      ui: {
        shown: "{n} показано",
        stores_total: "всего {n} точек",
        per_credit: "за кредит",
        show_more: "Показать ещё",
        show_less: "Свернуть",
        search_wide: "Искать игры, аркады, места...",
        search_narrow: "Поиск...",
        cab_model_unpublished: "Cabinet model not published",
        cab_model_unpublished_cap: "No listing says which cabinet this store runs. Official cab data covers Japan only, and community listings record the model just when someone noted it - so this is \"unknown\", not \"standard\".",
        offline_cab: "offline cabinet",
        offline_cabs: "offline cabinets",
        offline_cap: "This cabinet's network has shut down. It can still be played, but nothing is saved: no score history, no online play, no unlocks.",
        price_median: "{game}, median of {n} quoted prices in {country}. Not this store's own price.",
        price_sparse: "Based on only {n} listing(s) in {country}{for_game}, so treat it as a rough guide.",
        for_game: " for {game}",
        typical_country: "Typical for {country} - not this store's own price",
        permanently_closed: "Закрыто навсегда.",
        source: "источник",
        photo_by: "photo: {credit}",
        unknown_author: "unknown",
        listed: "в списке",
        size_1: "1 to 2 cabinets",
        size_2: "3 to 9 cabinets",
        size_3: "10 to 19 cabinets",
        size_4: "20 to 49 cabinets",
        size_5: "50 or more cabinets (mega arcade)",
        size_U: "Count unknown",
      }
    }
  };

  var current = "en";
  var listeners = [];
  var langBtn = null;
  var langMenu = null;
  var menuOpen = false;
  var inited = false;

  function dig(dict, key) {
    if (!dict || !key) return null;
    var parts = String(key).split(".");
    var cur = dict;
    for (var i = 0; i < parts.length; i++) {
      if (cur == null || typeof cur !== "object") return null;
      cur = cur[parts[i]];
    }
    return typeof cur === "string" ? cur : null;
  }

  function t(key, vars) {
    var s = dig(STRINGS[current], key);
    if (s == null) s = dig(STRINGS.en, key);
    if (s == null) s = key;
    if (vars) {
      s = s.replace(/\{(\w+)\}/g, function (_, k) {
        return vars[k] != null ? String(vars[k]) : "{" + k + "}";
      });
    }
    return s;
  }

  function htmlLang(code) {
    if (code === "zh-Hans") return "zh-Hans";
    if (code === "zh-Hant") return "zh-Hant";
    return code;
  }

  function normalizeTag(tag) {
    if (!tag) return null;
    var raw = String(tag).replace(/_/g, "-");
    var low = raw.toLowerCase();
    if (low === "zh-cn" || low === "zh-sg" || low === "zh-hans" ||
        low.indexOf("zh-hans") === 0) return "zh-Hans";
    if (low === "zh-tw" || low === "zh-hk" || low === "zh-mo" ||
        low === "zh-hant" || low.indexOf("zh-hant") === 0) return "zh-Hant";
    if (low === "zh") return "zh-Hans";
    if (low === "tl" || low.indexOf("fil") === 0 || low === "tl-ph") return "fil";
    var primary = low.split("-")[0];
    var map = {
      en: "en", ja: "ja", ko: "ko", id: "id", ms: "ms", th: "th",
      vi: "vi", es: "es", fr: "fr", de: "de", pt: "pt", it: "it", ru: "ru"
    };
    if (map[primary] && CODE_SET[map[primary]]) return map[primary];
    if (CODE_SET[raw]) return raw;
    return null;
  }

  function detect() {
    var stored = null;
    try { stored = localStorage.getItem(STORAGE_KEY); } catch (e) {}
    if (stored && CODE_SET[stored]) return stored;
    var nav = [];
    if (navigator.languages && navigator.languages.length) {
      for (var i = 0; i < navigator.languages.length; i++) nav.push(navigator.languages[i]);
    } else if (navigator.language) {
      nav.push(navigator.language);
    }
    for (var j = 0; j < nav.length; j++) {
      var code = normalizeTag(nav[j]);
      if (code) return code;
    }
    return "en";
  }

  function setEmptyMsg() {
    /* CSS content: var(--am-empty-msg) needs a quoted string value. */
    var msg = t("empty.map").replace(/\\/g, "\\\\").replace(/"/g, '\\"');
    try {
      document.documentElement.style.setProperty("--am-empty-msg", '"' + msg + '"');
    } catch (e) {}
  }

  function apply() {
    document.documentElement.lang = htmlLang(current);
    document.querySelectorAll("[data-i18n]").forEach(function (el) {
      var key = el.getAttribute("data-i18n");
      if (key) el.textContent = t(key);
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach(function (el) {
      var key = el.getAttribute("data-i18n-placeholder");
      if (key) el.setAttribute("placeholder", t(key));
    });
    document.querySelectorAll("[data-i18n-title]").forEach(function (el) {
      var key = el.getAttribute("data-i18n-title");
      if (key) el.setAttribute("title", t(key));
    });
    document.querySelectorAll("[data-i18n-aria]").forEach(function (el) {
      var key = el.getAttribute("data-i18n-aria");
      if (key) el.setAttribute("aria-label", t(key));
    });
    setEmptyMsg();
    if (langBtn) {
      langBtn.title = t("lang.button");
      langBtn.setAttribute("aria-label", t("lang.button"));
    }
    if (langMenu) langMenu.setAttribute("aria-label", t("lang.menu"));
    syncMenuActive();
    for (var i = 0; i < listeners.length; i++) {
      try { listeners[i](current); } catch (e) {}
    }
  }

  function setLang(code, opts) {
    opts = opts || {};
    if (!CODE_SET[code]) code = "en";
    if (code === current && !opts.force) {
      closeMenu();
      return;
    }
    current = code;
    try { localStorage.setItem(STORAGE_KEY, code); } catch (e) {}
    apply();
    closeMenu();
  }

  function syncMenuActive() {
    if (!langMenu) return;
    var items = langMenu.querySelectorAll("[data-lang]");
    for (var i = 0; i < items.length; i++) {
      var on = items[i].getAttribute("data-lang") === current;
      items[i].classList.toggle("on", on);
      items[i].setAttribute("aria-checked", on ? "true" : "false");
    }
  }

  function closeMenu() {
    menuOpen = false;
    if (langMenu) langMenu.hidden = true;
    if (langBtn) langBtn.setAttribute("aria-expanded", "false");
  }

  function openMenu() {
    menuOpen = true;
    if (langMenu) langMenu.hidden = false;
    if (langBtn) langBtn.setAttribute("aria-expanded", "true");
    syncMenuActive();
  }

  function toggleMenu() {
    if (menuOpen) closeMenu(); else openMenu();
  }

  /* Google-Translate-style mark: latin A + CJK glyph. */
  var LANG_ICON =
    '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">' +
    '<path fill="currentColor" d="M12.87 15.07l-2.54-2.51.03-.03A17.5 17.5 0 0 0 14.07 6H17V4h-7V2H8v2H1v2h11.17C11.5 7.92 10.44 9.75 9 11.35 8.07 10.32 7.3 9.19 6.69 8h-2c.73 1.63 1.73 3.17 2.98 4.56l-5.09 5.02L4 19l5-5 3.11 3.11.76-2.04zM18.5 10h-2L12 22h2l1.12-3h4.75L21 22h2l-4.5-12zm-2.62 7l1.62-4.33L19.12 17h-3.24z"/>' +
    "</svg>";

  function buildControl(beforeEl) {
    if (langBtn) return langBtn;

    var wrap = document.createElement("div");
    wrap.className = "am-lang-wrap";

    langBtn = document.createElement("button");
    langBtn.type = "button";
    langBtn.className = "am-lang-btn";
    langBtn.id = "lang-btn";
    langBtn.title = t("lang.button");
    langBtn.setAttribute("aria-label", t("lang.button"));
    langBtn.setAttribute("aria-haspopup", "listbox");
    langBtn.setAttribute("aria-expanded", "false");
    langBtn.setAttribute("aria-controls", "am-lang-menu");
    langBtn.innerHTML = LANG_ICON;
    langBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      toggleMenu();
    });

    langMenu = document.createElement("div");
    langMenu.id = "am-lang-menu";
    langMenu.className = "am-lang-menu";
    langMenu.setAttribute("role", "listbox");
    langMenu.setAttribute("aria-label", t("lang.menu"));
    langMenu.hidden = true;

    LANGS.forEach(function (L) {
      var item = document.createElement("button");
      item.type = "button";
      item.className = "am-lang-item";
      item.setAttribute("role", "option");
      item.setAttribute("data-lang", L.code);
      item.setAttribute("aria-checked", L.code === current ? "true" : "false");
      if (L.code === current) item.classList.add("on");
      item.textContent = L.native;
      item.addEventListener("click", function (e) {
        e.stopPropagation();
        setLang(L.code);
      });
      langMenu.appendChild(item);
    });

    wrap.appendChild(langBtn);
    wrap.appendChild(langMenu);

    if (beforeEl && beforeEl.parentNode) {
      beforeEl.parentNode.insertBefore(wrap, beforeEl);
    } else {
      var bar = document.getElementById("topbar");
      if (bar) bar.appendChild(wrap);
    }

    document.addEventListener("click", function (e) {
      if (!menuOpen) return;
      if (wrap.contains(e.target)) return;
      closeMenu();
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && menuOpen) {
        closeMenu();
        if (langBtn) langBtn.focus();
      }
    });

    return langBtn;
  }

  function on(fn) {
    if (typeof fn === "function") listeners.push(fn);
    return function off() {
      listeners = listeners.filter(function (f) { return f !== fn; });
    };
  }

  function init() {
    if (inited) {
      apply();
      return;
    }
    inited = true;
    current = detect();
    apply();
  }

  AM.i18n = {
    init: init,
    t: t,
    apply: apply,
    setLang: setLang,
    getLang: function () { return current; },
    langs: LANGS.slice(),
    buildControl: buildControl,
    on: on,
    STORAGE_KEY: STORAGE_KEY
  };
})(window.AM);
