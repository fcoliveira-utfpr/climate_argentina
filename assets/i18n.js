// ClimaTec AR — textos da interface em español (padrão), português e english.
// Uso: elementos com data-i18n="chave" recebem o texto; data-i18n-attr="placeholder:chave" para atributos.
const I18N = {
  es: {
    app_subtitulo: "Clasificaciones climáticas de la Argentina",
    sistema_activo: "Sistema activo",
    menu: "MENÚ",
    m_inicio: "Inicio", m_mapas: "Mapas", m_atlas: "Atlas",
    hero_titulo: "Mapeo de las clasificaciones climáticas de la Argentina",
    hero_texto: "Explore, por provincia y departamento (o partido), tres sistemas clásicos de clasificación climática — Köppen-Geiger, Thornthwaite y zonas de vida de Holdridge — calculados píxel a píxel (~1 km) a partir de las normales climatológicas 1991–2020 de CHELSA V2.1. Elija una clasificación para abrir el mapa interactivo con los datos mensuales de cada departamento.",
    card_koppen: "Clasificación climática mundial basada en la temperatura y la precipitación (Alvares et al., 2013; Kottek et al., 2006).",
    card_thornthwaite: "Clasificación basada en el balance hídrico climatológico (Thornthwaite y Mather, 1955; CAD = 100 mm): índice de humedad, variación estacional, eficiencia térmica y concentración estival.",
    card_holdridge: "Zonas de vida definidas por la biotemperatura, la precipitación anual y la razón de evapotranspiración potencial (ETP de Holdridge).",
    abrir_mapa: "Abrir mapa",
    rodape_dados: "Datos: CHELSA V2.1, normales 1991–2020 · Límites: GADM 4.1 · Cálculos: agrometeorologiapy",
    abrir_nueva_pestana: "Abrir en nueva pestaña",
    cerrar: "Cerrar",
    atlas_titulo: "Atlas climático de la Argentina",
    atlas_texto: "Mapas nacionales de las clasificaciones climáticas de Köppen-Geiger, Thornthwaite (1948) y Holdridge, y de las principales variables climatológicas asociadas, calculados píxel a píxel a partir de las normales 1991–2020 de CHELSA V2.1, y la validación con estaciones, la comparación con Beck et al. (2023) y el TerraClimate, la sensibilidad, la comparación con las ecorregiones y la estabilidad interanual de las clases. Haga clic en una figura para ampliarla.",
    figura: "Figura",
    cargando: "Cargando…",
    // página del mapa
    parametros: "Parámetros",
    provincia: "Provincia",
    todos_provincias: "Toda la Argentina",
    departamento: "Departamento / partido",
    seleccione_departamento: "Seleccione un departamento…",
    capa: "Capa",
    opacidad: "Opacidad",
    ayuda_clic: "Elija un departamento en la lista o haga clic en el mapa: verá el clima del punto clicado (~1 km) y todos los climas del departamento.",
    composicion: "Climas del departamento (% del área)",
    clima_punto: "Clima en el punto clicado",
    clima_aqui: "Clima en este punto",
    fuera_area: "Fuera del área clasificada",
    fuente_datos: "Fuente de datos",
    fuente_texto: "Normales 1991–2020 (CHELSA V2.1)<br>Resolución: ~1 km (30″)<br>Límites: GADM 4.1<br>Mapa: clasificación píxel a píxel con filtro de moda 3×3",
    clase_mayoritaria: "Clase mayoritaria",
    del_area: "del área del departamento",
    climograma: "Climograma mensual (normal 1991–2020, CHELSA V2.1)",
    precipitacion: "Precipitación (mm)",
    temp_media: "Temp. media (°C)",
    etp: "ETP Penman-Monteith (mm)",
    leyenda: "Leyenda",
    p_anual: "Precip. anual", p_mes_seco: "Precip. mes más seco",
    t_anual: "Temp. media anual", t_mes_frio: "Temp. mes más frío", t_mes_quente: "Temp. mes más cálido",
    pet_anual: "ETP anual",
    im: "Índice de humedad (Im)", ih: "Índice hídrico (Ih)", ia: "Índice de aridez (Ia)",
    def_anual: "Déficit hídrico anual", exc_anual: "Exceso hídrico anual",
    biotemp: "Biotemperatura", eth_anual: "ETP de Holdridge anual", razao_etp: "Razón ETP/P", estabilidad: "Estabilidad interanual de la clase",
    tipo_completo: "Tipo climático",
    th_umidade: "Humedad", th_subtipo: "Variación estacional", th_termica: "Eficiencia térmica",
    th_concentracao: "Concentración estival",
    meses: ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"],
    sin_datos: "Sin datos",
    error_carga: "Error al cargar los datos",
    listo: "listo ✓",
  },
  pt: {
    app_subtitulo: "Classificações climáticas da Argentina",
    sistema_activo: "Sistema ativo",
    menu: "MENU",
    m_inicio: "Início", m_mapas: "Mapas", m_atlas: "Atlas",
    hero_titulo: "Mapeamento das classificações climáticas da Argentina",
    hero_texto: "Explore, por província e departamento (ou partido), três sistemas clássicos de classificação climática — Köppen-Geiger, Thornthwaite e zonas de vida de Holdridge — calculados pixel a pixel (~1 km) a partir das normais climatológicas 1991–2020 do CHELSA V2.1. Escolha uma classificação para abrir o mapa interativo com os dados mensais de cada departamento.",
    card_koppen: "Classificação climática mundial baseada na temperatura e na precipitação (Alvares et al., 2013; Kottek et al., 2006).",
    card_thornthwaite: "Classificação baseada no balanço hídrico climatológico (Thornthwaite e Mather, 1955; CAD = 100 mm): índice de umidade, variação sazonal, eficiência térmica e concentração estival.",
    card_holdridge: "Zonas de vida definidas pela biotemperatura, pela precipitação anual e pela razão de evapotranspiração potencial (ETP de Holdridge).",
    abrir_mapa: "Abrir mapa",
    rodape_dados: "Dados: CHELSA V2.1, normais 1991–2020 · Limites: GADM 4.1 · Cálculos: agrometeorologiapy",
    abrir_nueva_pestana: "Abrir em nova aba",
    cerrar: "Fechar",
    atlas_titulo: "Atlas climático da Argentina",
    atlas_texto: "Mapas nacionais das classificações climáticas de Köppen-Geiger, Thornthwaite (1948) e Holdridge, e das principais variáveis climatológicas associadas, calculados pixel a pixel a partir das normais 1991–2020 do CHELSA V2.1, e a validação com estações, a comparação com Beck et al. (2023) e o TerraClimate, a sensibilidade, a comparação com as ecorregiões e a estabilidade interanual das classes. Clique numa figura para ampliá-la.",
    figura: "Figura",
    cargando: "Carregando…",
    parametros: "Parâmetros",
    provincia: "Província",
    todos_provincias: "Toda a Argentina",
    departamento: "Departamento / partido",
    seleccione_departamento: "Selecione um departamento…",
    capa: "Camada",
    opacidad: "Opacidade",
    ayuda_clic: "Escolha um departamento na lista ou clique no mapa: verá o clima do ponto clicado (~1 km) e todos os climas do departamento.",
    composicion: "Climas do departamento (% da área)",
    clima_punto: "Clima no ponto clicado",
    clima_aqui: "Clima neste ponto",
    fuera_area: "Fora da área classificada",
    fuente_datos: "Fonte de dados",
    fuente_texto: "Normais 1991–2020 (CHELSA V2.1)<br>Resolução: ~1 km (30″)<br>Limites: GADM 4.1<br>Mapa: classificação pixel a pixel com filtro de moda 3×3",
    clase_mayoritaria: "Classe majoritária",
    del_area: "da área do departamento",
    climograma: "Climograma mensal (normal 1991–2020, CHELSA V2.1)",
    precipitacion: "Precipitação (mm)",
    temp_media: "Temp. média (°C)",
    etp: "ETP Penman-Monteith (mm)",
    leyenda: "Legenda",
    p_anual: "Precip. anual", p_mes_seco: "Precip. mês mais seco",
    t_anual: "Temp. média anual", t_mes_frio: "Temp. mês mais frio", t_mes_quente: "Temp. mês mais quente",
    pet_anual: "ETP anual",
    im: "Índice de umidade (Im)", ih: "Índice hídrico (Ih)", ia: "Índice de aridez (Ia)",
    def_anual: "Deficiência hídrica anual", exc_anual: "Excedente hídrico anual",
    biotemp: "Biotemperatura", eth_anual: "ETP de Holdridge anual", razao_etp: "Razão ETP/P", estabilidad: "Estabilidade interanual da classe",
    tipo_completo: "Tipo climático",
    th_umidade: "Umidade", th_subtipo: "Variação sazonal", th_termica: "Eficiência térmica",
    th_concentracao: "Concentração estival",
    meses: ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"],
    sin_datos: "Sem dados",
    error_carga: "Erro ao carregar os dados",
    listo: "pronto ✓",
  },
  en: {
    app_subtitulo: "Climate classifications of Argentina",
    sistema_activo: "System online",
    menu: "MENU",
    m_inicio: "Home", m_mapas: "Maps", m_atlas: "Atlas",
    hero_titulo: "Mapping the climate classifications of Argentina",
    hero_texto: "Explore, by province and department (or partido), three classic climate classification systems — Köppen-Geiger, Thornthwaite and Holdridge life zones — computed pixel by pixel (~1 km) from the 1991–2020 climate normals of CHELSA V2.1. Choose a classification to open the interactive map with the monthly data of each department.",
    card_koppen: "Worldwide climate classification based on temperature and precipitation (Alvares et al., 2013; Kottek et al., 2006).",
    card_thornthwaite: "Classification based on the climatological water balance (Thornthwaite and Mather, 1955; AWC = 100 mm): moisture index, seasonal variation, thermal efficiency and summer concentration.",
    card_holdridge: "Life zones defined by biotemperature, annual precipitation and the potential evapotranspiration ratio (Holdridge PET).",
    abrir_mapa: "Open map",
    rodape_dados: "Data: CHELSA V2.1, 1991–2020 normals · Boundaries: GADM 4.1 · Computation: agrometeorologiapy",
    abrir_nueva_pestana: "Open in new tab",
    cerrar: "Close",
    atlas_titulo: "Climate atlas of Argentina",
    atlas_texto: "National maps of the Köppen-Geiger, Thornthwaite (1948) and Holdridge climate classifications, and of the main associated climatological variables, computed pixel by pixel from the 1991–2020 CHELSA V2.1 normals, plus the station validation, the comparison with Beck et al. (2023) and TerraClimate, the sensitivity analysis, the comparison with ecoregions and the interannual stability of the classes. Click a figure to enlarge it.",
    figura: "Figure",
    cargando: "Loading…",
    parametros: "Parameters",
    provincia: "Province",
    todos_provincias: "All of Argentina",
    departamento: "Department / partido",
    seleccione_departamento: "Select a department…",
    capa: "Layer",
    opacidad: "Opacity",
    ayuda_clic: "Pick a department from the list or click on the map: you will see the climate at the clicked point (~1 km) and all climates of the department.",
    composicion: "Climates of the department (% of area)",
    clima_punto: "Climate at the clicked point",
    clima_aqui: "Climate at this point",
    fuera_area: "Outside the classified area",
    fuente_datos: "Data source",
    fuente_texto: "1991–2020 normals (CHELSA V2.1)<br>Resolution: ~1 km (30″)<br>Boundaries: GADM 4.1<br>Map: pixel-based classification with a 3×3 mode filter",
    clase_mayoritaria: "Majority class",
    del_area: "of the department area",
    climograma: "Monthly climate chart (1991–2020 normal, CHELSA V2.1)",
    precipitacion: "Precipitation (mm)",
    temp_media: "Mean temp. (°C)",
    etp: "Penman-Monteith PET (mm)",
    leyenda: "Legend",
    p_anual: "Annual precip.", p_mes_seco: "Driest-month precip.",
    t_anual: "Mean annual temp.", t_mes_frio: "Coldest-month temp.", t_mes_quente: "Warmest-month temp.",
    pet_anual: "Annual PET",
    im: "Moisture index (Im)", ih: "Humidity index (Ih)", ia: "Aridity index (Ia)",
    def_anual: "Annual water deficit", exc_anual: "Annual water surplus",
    biotemp: "Biotemperature", eth_anual: "Annual Holdridge PET", razao_etp: "PET/P ratio", estabilidad: "Interannual class stability",
    tipo_completo: "Climate type",
    th_umidade: "Moisture", th_subtipo: "Seasonal variation", th_termica: "Thermal efficiency",
    th_concentracao: "Summer concentration",
    meses: ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"],
    sin_datos: "No data",
    error_carga: "Error loading data",
    listo: "ready ✓",
  },
};

const IDIOMAS = ["es", "pt", "en"];
const LOCALE = { es: "es-AR", pt: "pt-BR", en: "en-US" };

function idiomaAtual() {
  const p = new URLSearchParams(location.search).get("lang");
  if (IDIOMAS.includes(p)) return p;
  try { const s = localStorage.getItem("climatec_ar_lang"); if (IDIOMAS.includes(s)) return s; } catch (e) {}
  return "es";
}
let LANG = idiomaAtual();
const t = (k) => (I18N[LANG] && I18N[LANG][k] !== undefined) ? I18N[LANG][k] : (I18N.es[k] ?? k);

function aplicarIdioma() {
  document.documentElement.lang = LANG;
  document.querySelectorAll("[data-i18n]").forEach(el => { el.innerHTML = t(el.dataset.i18n); });
  document.querySelectorAll("[data-i18n-attr]").forEach(el => {
    el.dataset.i18nAttr.split(";").forEach(par => { const [a, k] = par.split(":"); el.setAttribute(a, t(k)); });
  });
  document.querySelectorAll(".lang-btn").forEach(b => {
    const ativo = b.dataset.lang === LANG;
    b.classList.toggle("bg-[#2B6CB0]", ativo); b.classList.toggle("text-white", ativo);
    b.classList.toggle("text-slate-600", !ativo);
  });
}

function trocarIdioma(lg) {
  if (!IDIOMAS.includes(lg) || lg === LANG) return;
  LANG = lg;
  try { localStorage.setItem("climatec_ar_lang", lg); } catch (e) {}
  const u = new URL(location.href); u.searchParams.set("lang", lg); history.replaceState(null, "", u);
  aplicarIdioma();
  document.dispatchEvent(new CustomEvent("idioma", { detail: lg }));
}
