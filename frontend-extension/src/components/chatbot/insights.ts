/**
 * Curated dynamic insights and fun facts based on authentic IDMC Pemda DIY datasets.
 * Used for the 2-minute proactive engagement nudge.
 * Strictly 0 emotes to ensure professional, non-slop government digital service.
 */

export interface DynamicInsight {
  id: string
  title: string
  fact: string
  suggestedPrompt: string
}

export const DYNAMIC_INSIGHTS_POOL: DynamicInsight[] = [
  {
    id: 'apbd-pembangunan',
    title: 'Realisasi Belanja & Pembangunan DIY',
    fact: 'Pemerintah Daerah DIY mencatat realisasi anggaran belanja dan program pembangunan fisik serta non-fisik secara transparan yang dipantau melalui Dashboard Pembangunan IDMC.',
    suggestedPrompt: 'Bagaimana realisasi belanja dan pembangunan di Pemda DIY?',
  },
  {
    id: 'fiber-optic',
    title: 'Infrastruktur Jaringan Fiber Optic',
    fact: 'Diskominfo DIY mengelola infrastruktur jaringan intra-pemerintah dengan bentangan kabel fiber optic bawah tanah dan udara yang menghubungkan seluruh OPD hingga kantor layanan publik di DIY.',
    suggestedPrompt: 'Berapa panjang kabel jaringan fiber optic di Pemda DIY?',
  },
  {
    id: 'cctv-surveillance',
    title: 'Integrasi CCTV & Surveillance Malioboro',
    fact: 'Portal IDMC memantau ratusan titik kamera CCTV publik secara langsung, mencakup ATCS lalu lintas perkotaan, kawasan wisata pedestrian Malioboro, hingga pantauan debit air sungai.',
    suggestedPrompt: 'Tampilkan informasi titik CCTV publik dan lalu lintas di Jogja.',
  },
  {
    id: 'spbe-smart-province',
    title: 'Arsitektur SPBE & Jogja Smart Province',
    fact: 'Pemda DIY mengimplementasikan Peta Rencana Sistem Pemerintahan Berbasis Elektronik (SPBE) dan Masterplan Jogja Smart Province untuk integrasi layanan publik digital.',
    suggestedPrompt: 'Jelaskan rencana SPBE dan Masterplan Jogja Smart Province.',
  },
  {
    id: 'kepegawaian-simpeg',
    title: 'Profil Kepegawaian ASN Pemda DIY',
    fact: 'Data kepegawaian ASN di lingkungan Pemda DIY tercatat secara terpusat di Dashboard Simpeg, menyajikan komposisi jabatan, jenjang kepangkatan, dan distribusi pegawai di seluruh OPD.',
    suggestedPrompt: 'Berapa jumlah ASN dan bagaimana persebaran OPD di Pemda DIY?',
  },
  {
    id: 'ikm-umkm-disperindag',
    title: 'Sentra Industri Kecil & Menengah (IKM)',
    fact: 'Dinas Perindustrian dan Perdagangan DIY mencatat lebih dari 245 sentra Industri Kecil dan Menengah (IKM) aktif yang tersebar di Sleman, Bantul, Kulon Progo, Gunungkidul, dan Kota Yogyakarta.',
    suggestedPrompt: 'Berapa jumlah sentra industri kecil dan menengah (IKM) di DIY?',
  },
  {
    id: 'perkebunan-komoditas',
    title: 'Potensi Sektor Perkebunan DIY',
    fact: 'Data komoditas perkebunan di DIY mencakup produksi tanaman pangan dan komoditas unggulan di kabupaten Sleman, Bantul, Kulon Progo, Gunungkidul, dan Kota Yogyakarta.',
    suggestedPrompt: 'Apa saja data komoditas perkebunan yang tercatat di IDMC?',
  },
  {
    id: 'ketahanan-pangan',
    title: 'Indeks Ketahanan Pangan & Pasokan Komoditas',
    fact: 'Dashboard Ketahanan Pangan IDMC memantau neraca ketersediaan bahan pokok, stabilitas pasokan pangan, serta tingkat kerentanan pangan antar wilayah di DIY.',
    suggestedPrompt: 'Bagaimana kondisi ketahanan pangan dan ketersediaan bahan pokok di DIY?',
  },
  {
    id: 'lingkungan-hidup',
    title: 'Kualitas Lingkungan Hidup & Udara DIY',
    fact: 'Dinas Lingkungan Hidup dan Kehutanan DIY mencatat indeks kualitas lingkungan hidup (IKLH) yang memadukan indeks kualitas air, kualitas udara, dan tutupan lahan di seluruh DIY.',
    suggestedPrompt: 'Bagaimana status indeks kualitas lingkungan hidup dan kualitas udara di DIY?',
  },
  {
    id: 'kependudukan-demografi',
    title: 'Demografi Penduduk & Layanan Kapanewon',
    fact: 'IDMC mengintegrasikan statistik kependudukan DIY, piramida usia penduduk, hingga kepadatan sebaran warga di 78 kapanewon dan kemantren se-DIY.',
    suggestedPrompt: 'Berapa jumlah penduduk DIY dan persebarannya di kabupaten dan kota?',
  },
]

/** Formats an insight into a polished Markdown message for the assistant (0 emotes) */
export function formatInsightMessage(insight: DynamicInsight): string {
  const encodedPrompt = encodeURIComponent(insight.suggestedPrompt)
  return (
    `**Sekilas Data DIY: ${insight.title}**\n\n` +
    `${insight.fact}\n\n` +
    `Mau tahu lebih lanjut? [Klik di sini: "${insight.suggestedPrompt}"](idmc-prompt:${encodedPrompt})`
  )
}
