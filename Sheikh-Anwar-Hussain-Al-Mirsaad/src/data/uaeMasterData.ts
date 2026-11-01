import { 
  Business, 
  BusinessCategory, 
  CollectionJob, 
  CrmLead, 
  DuplicateCandidate, 
  Emirate, 
  SuppressionRecord, 
  TeamMember, 
  AuditLog 
} from '../types/index.ts';

export const UAE_EMIRATES: { name: Emirate; arName: string; capital: string; commercialAreas: string[] }[] = [
  {
    name: 'Dubai',
    arName: 'دبي',
    capital: 'Dubai City',
    commercialAreas: [
      'Business Bay',
      'Downtown Dubai',
      'DIFC',
      'Al Quoz Industrial',
      'Dubai Marina',
      'Jumeirah Lakes Towers (JLT)',
      'Deira Commercial',
      'Al Barsha',
      'Dubai Silicon Oasis',
      'Jebel Ali Free Zone (JAFZA)'
    ]
  },
  {
    name: 'Abu Dhabi',
    arName: 'أبوظبي',
    capital: 'Abu Dhabi',
    commercialAreas: [
      'Al Maryah Island (ADGM)',
      'Corniche Area',
      'Musaffah Industrial',
      'Al Reem Island',
      'Khalifa City',
      'Masdar City Free Zone',
      'Industrial City of Abu Dhabi (ICAD)'
    ]
  },
  {
    name: 'Sharjah',
    arName: 'الشارقة',
    capital: 'Sharjah City',
    commercialAreas: [
      'Al Majaz Waterfront',
      'Sharjah Industrial Area',
      'Muwaileh Commercial',
      'SAIF Zone',
      'Al Nahda',
      'Al Khan'
    ]
  },
  {
    name: 'Ajman',
    arName: 'عجمان',
    capital: 'Ajman City',
    commercialAreas: [
      'Ajman Free Zone',
      'Al Nuaimiya',
      'Al Jurf Industrial Area',
      'Al Rashidiya Commercial'
    ]
  },
  {
    name: 'Ras Al Khaimah',
    arName: 'رأس الخيمة',
    capital: 'Ras Al Khaimah',
    commercialAreas: [
      'Al Nakheel Commercial',
      'RAK Economic Zone (RAKEZ)',
      'Al Hamra Business Village',
      'Khuzam Business District'
    ]
  },
  {
    name: 'Fujairah',
    arName: 'الفجيرة',
    capital: 'Fujairah City',
    commercialAreas: [
      'Fujairah Free Zone',
      'Hamad Bin Abdulla Commercial St',
      'Al Faseel District',
      'Fujairah Oil Industry Zone (FOIZ)'
    ]
  },
  {
    name: 'Umm Al Quwain',
    arName: 'أم القيوين',
    capital: 'Umm Al Quwain',
    commercialAreas: [
      'UAQ Free Trade Zone',
      'Al Salamah Commercial',
      'Old Town Commercial Area'
    ]
  }
];

export const INITIAL_CATEGORIES: BusinessCategory[] = [
  {
    id: 'cat-1',
    nameEn: 'Construction and contracting',
    nameAr: 'البناء والتشييد والمقاولات',
    slug: 'construction-contracting',
    icon: 'HardHat',
    businessCount: 1420,
    subcategories: ['General Contracting', 'MEP Engineering', 'Civil Infrastructure', 'Interior Fitout', 'Facade Engineering']
  },
  {
    id: 'cat-2',
    nameEn: 'Real estate',
    nameAr: 'العقارات والوساطة العقارية',
    slug: 'real-estate',
    icon: 'Building2',
    businessCount: 2150,
    subcategories: ['Property Brokerage', 'Property Management', 'Commercial Leasing', 'Developer Sales', 'Facility Management']
  },
  {
    id: 'cat-3',
    nameEn: 'Restaurants and cafes',
    nameAr: 'المطاعم والمقاهي والضيافة',
    slug: 'restaurants-cafes',
    icon: 'UtensilsCrossed',
    businessCount: 3890,
    subcategories: ['Fine Dining', 'Casual Dining', 'Specialty Coffee', 'Catering Services', 'Cloud Kitchens']
  },
  {
    id: 'cat-4',
    nameEn: 'Healthcare and clinics',
    nameAr: 'الرعاية الصحية والعيادات',
    slug: 'healthcare-clinics',
    icon: 'Activity',
    businessCount: 980,
    subcategories: ['Multi-specialty Clinics', 'Dental Clinics', 'Aesthetic & Dermatology', 'Pharmacies', 'Medical Equipment']
  },
  {
    id: 'cat-5',
    nameEn: 'Logistics and transport',
    nameAr: 'اللوجستيات والشحن والنقل',
    slug: 'logistics-transport',
    icon: 'Truck',
    businessCount: 1640,
    subcategories: ['Freight Forwarding', 'Warehousing & 3PL', 'Last-mile Delivery', 'Cold Chain Transport', 'Fleet Management']
  },
  {
    id: 'cat-6',
    nameEn: 'IT and software companies',
    nameAr: 'تكنولوجيا المعلومات والبرمجيات',
    slug: 'it-software',
    icon: 'Cpu',
    businessCount: 1890,
    subcategories: ['Enterprise SaaS', 'Cloud & Cybersecurity', 'Custom App Development', 'AI & Data Analytics', 'Managed IT Services']
  },
  {
    id: 'cat-7',
    nameEn: 'Financial and professional services',
    nameAr: 'الخدمات المالية والاستشارية',
    slug: 'financial-professional',
    icon: 'Briefcase',
    businessCount: 1320,
    subcategories: ['Auditing & Tax Accounting', 'Corporate Legal Services', 'Management Consulting', 'Wealth Management', 'PRO & Company Setup']
  },
  {
    id: 'cat-8',
    nameEn: 'Manufacturing and factories',
    nameAr: 'التصنيع والمصانع',
    slug: 'manufacturing-factories',
    icon: 'Factory',
    businessCount: 840,
    subcategories: ['Building Materials', 'FMCG & Food Processing', 'Metal & Steel Fabrication', 'Plastics & Packaging', 'Chemical Products']
  },
  {
    id: 'cat-9',
    nameEn: 'Wholesale and trading companies',
    nameAr: 'تجارة الجملة والاستيراد والتصدير',
    slug: 'wholesale-trading',
    icon: 'Boxes',
    businessCount: 2450,
    subcategories: ['General Trading LLC', 'Electronics Wholesale', 'FMCG Trading', 'Textile Import/Export', 'Automotive Parts Distribution']
  },
  {
    id: 'cat-10',
    nameEn: 'Automobile services',
    nameAr: 'خدمات وصيانة السيارات',
    slug: 'automobile-services',
    icon: 'Car',
    businessCount: 920,
    subcategories: ['Auto Repair Garages', 'Authorized Service Centers', 'Tire & Battery Centers', 'Car Detailing & Wrap', 'Commercial Fleet Maintenance']
  },
  {
    id: 'cat-11',
    nameEn: 'Cleaning and maintenance',
    nameAr: 'خدمات التنظيف والصيانة العامة',
    slug: 'cleaning-maintenance',
    icon: 'Sparkles',
    businessCount: 1110,
    subcategories: ['Commercial Cleaning', 'HVAC Air Conditioning Services', 'Pest Control', 'Deep Sanitization', 'Rope Access & Window Cleaning']
  },
  {
    id: 'cat-12',
    nameEn: 'Marketing agencies',
    nameAr: 'وكالات التسويق والدعاية والإعلان',
    slug: 'marketing-agencies',
    icon: 'Megaphone',
    businessCount: 890,
    subcategories: ['Digital Performance Marketing', 'PR & Media Relations', 'SEO & Web Design', 'Outdoor & Billboard Advertising', 'Social Media Production']
  },
  {
    id: 'cat-13',
    nameEn: 'Hotels and hospitality',
    nameAr: 'الفنادق والضيافة والسياحة',
    slug: 'hotels-hospitality',
    icon: 'Hotel',
    businessCount: 680,
    subcategories: ['5-Star Luxury Hotels', 'Boutique Resorts', 'Serviced Hotel Apartments', 'DMC Tour Operators', 'Event & Exhibition Venues']
  },
  {
    id: 'cat-14',
    nameEn: 'Retail and supermarkets',
    nameAr: 'متاجر التجزئة والسوبرماركت',
    slug: 'retail-supermarkets',
    icon: 'ShoppingBag',
    businessCount: 3100,
    subcategories: ['Hypermarkets', 'Luxury Boutiques', 'Electronics Retail', 'Specialty Gourmet Stores', 'Pharmacy Chains']
  },
  {
    id: 'cat-15',
    nameEn: 'Beauty salons and spas',
    nameAr: 'صالونات التجميل والسبا',
    slug: 'beauty-salons-spas',
    icon: 'Smile',
    businessCount: 1450,
    subcategories: ['Luxury Ladies Spas', 'Executive Barbershops', 'Medical Aesthetics', 'Nail & Wellness Lounges']
  },
  {
    id: 'cat-16',
    nameEn: 'Education and training',
    nameAr: 'التعليم والتدريب الأكاديمي',
    slug: 'education-training',
    icon: 'GraduationCap',
    businessCount: 620,
    subcategories: ['International Schools', 'Universities & Colleges', 'Corporate Training Institutes', 'Language & Tech Academies']
  },
  {
    id: 'cat-17',
    nameEn: 'E-commerce businesses',
    nameAr: 'شركات التجارة الإلكترونية',
    slug: 'ecommerce-businesses',
    icon: 'Globe',
    businessCount: 1250,
    subcategories: ['Direct-to-Consumer (D2C)', 'B2B Marketplaces', 'Subscription Commerce', 'Cross-border Fulfillment']
  }
];

export const INITIAL_BUSINESSES: Business[] = [
  {
    id: 'biz-dxb-001',
    nameEn: 'Al Naboodah Construction Group LLC',
    nameAr: 'مجموعة النابودة للمقاولات ش.ذ.م.م',
    normalizedName: 'al naboodah construction group',
    category: 'Construction and contracting',
    subcategory: 'Civil Infrastructure',
    description: 'One of the leading civil engineering and building construction conglomerates in the UAE delivering iconic infrastructure projects.',
    emirate: 'Dubai',
    city: 'Dubai',
    area: 'Al Quoz Industrial',
    streetAddress: '8th Street, Al Quoz 3, Industrial Area',
    buildingName: 'Al Naboodah Headquarters',
    latitude: 25.1312,
    longitude: 55.2341,
    websiteUrl: 'https://alnaboodahconstruction.com',
    primaryPhone: '+971 4 294 8888',
    normalizedPhone: '+97142948888',
    primaryEmail: 'info@alnaboodahconstruction.com',
    whatsappNumber: '+971509876543',
    socialLinks: {
      linkedin: 'https://linkedin.com/company/al-naboodah-construction',
      twitter: 'https://twitter.com/alnaboodahgroup'
    },
    operatingHours: 'Mon-Fri: 08:00 - 17:30',
    tradeLicenseNumber: 'DXB-CN-189422',
    sourcePlatform: 'google_places',
    sources: [
      { platform: 'google_places', externalId: 'ChIJx_9fU1tDXz4Rk8A...', discoveredAt: '2026-08-14', lastVerifiedAt: '2026-10-15', isPrimary: true },
      { platform: 'ded_registry', externalId: 'DED-189422', discoveredAt: '2026-08-15', lastVerifiedAt: '2026-10-15' },
      { platform: '2gis', externalId: '2gis-ae-98124', discoveredAt: '2026-09-02', lastVerifiedAt: '2026-10-20' }
    ],
    dateDiscovered: '2026-08-14T09:30:00Z',
    dateLastVerified: '2026-10-20T11:00:00Z',
    qualityScore: 98,
    crmLeadStatus: 'in_pipeline',
    crmLeadId: 'lead-001'
  },
  {
    id: 'biz-dxb-002',
    nameEn: 'Espace Real Estate Brokerage',
    nameAr: 'إسباس للوساطة العقارية',
    normalizedName: 'espace real estate brokerage',
    category: 'Real estate',
    subcategory: 'Property Brokerage',
    description: 'Award-winning luxury real estate brokerage agency specializing in high-end Dubai prime residential communities and commercial towers.',
    emirate: 'Dubai',
    city: 'Dubai',
    area: 'Dubai Marina',
    streetAddress: 'Office 2702, Marina Plaza, Dubai Marina',
    buildingName: 'Marina Plaza Commercial Tower',
    latitude: 25.0768,
    longitude: 55.1415,
    websiteUrl: 'https://espace.ae',
    primaryPhone: '+971 4 306 9999',
    normalizedPhone: '+97143069999',
    primaryEmail: 'commercial@espace.ae',
    whatsappNumber: '+971521234567',
    socialLinks: {
      linkedin: 'https://linkedin.com/company/espace-real-estate',
      instagram: 'https://instagram.com/espacerealestate'
    },
    operatingHours: 'Mon-Sat: 09:00 - 18:00',
    tradeLicenseNumber: 'DXB-RE-592031',
    sourcePlatform: 'google_places',
    sources: [
      { platform: 'google_places', discoveredAt: '2026-09-01', lastVerifiedAt: '2026-10-22', isPrimary: true },
      { platform: 'uae_yellowpages', discoveredAt: '2026-09-05', lastVerifiedAt: '2026-10-18' }
    ],
    dateDiscovered: '2026-09-01T14:20:00Z',
    dateLastVerified: '2026-10-22T08:15:00Z',
    qualityScore: 95,
    crmLeadStatus: 'in_pipeline',
    crmLeadId: 'lead-002'
  },
  {
    id: 'biz-dxb-003',
    nameEn: 'Apex Cloud Solutions FZ-LLC',
    nameAr: 'حلول أبيكس السحابية',
    normalizedName: 'apex cloud solutions',
    category: 'IT and software companies',
    subcategory: 'Cloud & Cybersecurity',
    description: 'Premier cloud architecture, cyber defense, and enterprise systems integrator serving Gulf banking, logistics, and government entities.',
    emirate: 'Dubai',
    city: 'Dubai',
    area: 'Dubai Silicon Oasis',
    streetAddress: 'High Tech Ecosystem Bldg, DTEC Complex, DSO',
    buildingName: 'DTEC TechnoHub',
    latitude: 25.1224,
    longitude: 55.3789,
    websiteUrl: 'https://apexcloud.ae',
    primaryPhone: '+971 4 501 5555',
    normalizedPhone: '+97145015555',
    primaryEmail: 'enterprise@apexcloud.ae',
    whatsappNumber: '+971556789012',
    socialLinks: {
      linkedin: 'https://linkedin.com/company/apex-cloud-uae'
    },
    operatingHours: 'Sun-Thu: 08:30 - 17:30',
    tradeLicenseNumber: 'DSO-FZE-78411',
    sourcePlatform: 'web_crawl',
    sources: [
      { platform: 'web_crawl', discoveredAt: '2026-09-12', lastVerifiedAt: '2026-10-25', isPrimary: true },
      { platform: 'google_places', discoveredAt: '2026-09-14', lastVerifiedAt: '2026-10-25' }
    ],
    dateDiscovered: '2026-09-12T10:00:00Z',
    dateLastVerified: '2026-10-25T16:30:00Z',
    qualityScore: 92,
    crmLeadStatus: 'in_pipeline',
    crmLeadId: 'lead-003'
  },
  {
    id: 'biz-auh-001',
    nameEn: 'Al Faraa Integrated Construction Group',
    nameAr: 'مجموعة الفارعة للمقاولات المتكاملة',
    normalizedName: 'al faraa integrated construction group',
    category: 'Construction and contracting',
    subcategory: 'General Contracting',
    description: 'Grade A turnkey infrastructure, commercial towers, and industrial construction services across the Emirate of Abu Dhabi.',
    emirate: 'Abu Dhabi',
    city: 'Abu Dhabi',
    area: 'Musaffah Industrial',
    streetAddress: 'Plot 44, Sector M-12, Musaffah Industrial Zone',
    buildingName: 'Al Faraa Towers',
    latitude: 24.3644,
    longitude: 54.4981,
    websiteUrl: 'https://alfaraagroup.com',
    primaryPhone: '+971 2 551 2222',
    normalizedPhone: '+97125512222',
    primaryEmail: 'tenders@alfaraagroup.com',
    whatsappNumber: '+971503344556',
    operatingHours: 'Mon-Sat: 07:30 - 17:00',
    tradeLicenseNumber: 'AUH-CN-339102',
    sourcePlatform: '2gis',
    sources: [
      { platform: '2gis', discoveredAt: '2026-08-20', lastVerifiedAt: '2026-10-18', isPrimary: true },
      { platform: 'google_places', discoveredAt: '2026-08-22', lastVerifiedAt: '2026-10-18' }
    ],
    dateDiscovered: '2026-08-20T11:15:00Z',
    dateLastVerified: '2026-10-18T14:40:00Z',
    qualityScore: 91,
    crmLeadStatus: 'lead_created',
    crmLeadId: 'lead-004'
  },
  {
    id: 'biz-auh-002',
    nameEn: 'Capital Health Medical Clinics & Polyclinic',
    nameAr: 'عيادات كابيتال هيلث الطبية متعددة التخصصات',
    normalizedName: 'capital health medical clinics',
    category: 'Healthcare and clinics',
    subcategory: 'Multi-specialty Clinics',
    description: 'Accredited multi-specialty clinical network providing cardiology, orthopedics, family medicine, and advanced diagnostics in the capital.',
    emirate: 'Abu Dhabi',
    city: 'Abu Dhabi',
    area: 'Corniche Area',
    streetAddress: 'Corniche West Road, Al Bateen District',
    buildingName: 'Al Bateen Healthcare Center',
    latitude: 24.4682,
    longitude: 54.3411,
    websiteUrl: 'https://capitalhealth.ae',
    primaryPhone: '+971 2 639 9000',
    normalizedPhone: '+97126399000',
    primaryEmail: 'appointments@capitalhealth.ae',
    whatsappNumber: '+971507788990',
    socialLinks: {
      instagram: 'https://instagram.com/capitalhealthuae'
    },
    operatingHours: 'Sun-Fri: 08:00 - 21:00',
    tradeLicenseNumber: 'AUH-HC-88120',
    sourcePlatform: 'google_places',
    sources: [
      { platform: 'google_places', discoveredAt: '2026-09-04', lastVerifiedAt: '2026-10-21', isPrimary: true }
    ],
    dateDiscovered: '2026-09-04T08:45:00Z',
    dateLastVerified: '2026-10-21T12:00:00Z',
    qualityScore: 94,
    crmLeadStatus: 'unassigned'
  },
  {
    id: 'biz-shj-001',
    nameEn: 'Sharjah Freight Line Logistics LLC',
    nameAr: 'خط الشارقة للشحن واللوجستيات ش.ذ.م.م',
    normalizedName: 'sharjah freight line logistics',
    category: 'Logistics and transport',
    subcategory: 'Freight Forwarding',
    description: 'Multimodal air, sea, and land customs brokerage with expansive temperature-controlled bonded warehouses in SAIF Zone.',
    emirate: 'Sharjah',
    city: 'Sharjah',
    area: 'SAIF Zone',
    streetAddress: 'Warehouse Q3-044, Sharjah Airport International Free Zone',
    buildingName: 'SAIF Zone Logistics Hub',
    latitude: 25.3289,
    longitude: 55.5178,
    websiteUrl: 'https://shjfreight.com',
    primaryPhone: '+971 6 557 4444',
    normalizedPhone: '+97165574444',
    primaryEmail: 'cargo@shjfreight.com',
    whatsappNumber: '+971569988771',
    operatingHours: 'Mon-Sat: 08:00 - 18:00',
    tradeLicenseNumber: 'SHJ-FZ-5412',
    sourcePlatform: '2gis',
    sources: [
      { platform: '2gis', discoveredAt: '2026-09-10', lastVerifiedAt: '2026-10-23', isPrimary: true },
      { platform: 'uae_yellowpages', discoveredAt: '2026-09-12', lastVerifiedAt: '2026-10-23' }
    ],
    dateDiscovered: '2026-09-10T12:00:00Z',
    dateLastVerified: '2026-10-23T15:10:00Z',
    qualityScore: 89,
    crmLeadStatus: 'in_pipeline',
    crmLeadId: 'lead-005'
  },
  {
    id: 'biz-shj-002',
    nameEn: 'Al Andalus Auditing & Tax Advisors',
    nameAr: 'الأندلس لتدقيق الحسابات والاستشارات الضريبية',
    normalizedName: 'al andalus auditing tax advisors',
    category: 'Financial and professional services',
    subcategory: 'Auditing & Tax Accounting',
    description: 'FTA registered certified tax agents, corporate tax structuring, statutory financial audits, and VAT advisory.',
    emirate: 'Sharjah',
    city: 'Sharjah',
    area: 'Al Majaz Waterfront',
    streetAddress: 'Corniche Street, Al Majaz 2',
    buildingName: 'Al Majaz Pearl Tower, 14th Floor',
    latitude: 25.3351,
    longitude: 55.3854,
    websiteUrl: 'https://alandalustax.ae',
    primaryPhone: '+971 6 528 7770',
    normalizedPhone: '+97165287770',
    primaryEmail: 'audit@alandalustax.ae',
    whatsappNumber: '+971501122334',
    operatingHours: 'Sun-Thu: 09:00 - 17:30',
    tradeLicenseNumber: 'SHJ-PR-7741',
    sourcePlatform: 'ded_registry',
    sources: [
      { platform: 'ded_registry', discoveredAt: '2026-08-30', lastVerifiedAt: '2026-10-19', isPrimary: true }
    ],
    dateDiscovered: '2026-08-30T10:15:00Z',
    dateLastVerified: '2026-10-19T09:30:00Z',
    qualityScore: 90,
    crmLeadStatus: 'unassigned'
  },
  {
    id: 'biz-ajm-001',
    nameEn: 'Emirates Precision Metal Fabrication LLC',
    nameAr: 'الإمارات للأشغال المعدنية الدقيقة ش.ذ.م.م',
    normalizedName: 'emirates precision metal fabrication',
    category: 'Manufacturing and factories',
    subcategory: 'Metal & Steel Fabrication',
    description: 'CNC high-precision sheet metal bending, laser cutting, and architectural stainless steel fabrication facility.',
    emirate: 'Ajman',
    city: 'Ajman',
    area: 'Al Jurf Industrial Area',
    streetAddress: 'Street 19, Al Jurf Industrial 2',
    buildingName: 'Factory Compound Plot 88',
    latitude: 25.4321,
    longitude: 55.5122,
    websiteUrl: 'https://emiratesprecision.ae',
    primaryPhone: '+971 6 743 1188',
    normalizedPhone: '+97167431188',
    primaryEmail: 'sales@emiratesprecision.ae',
    whatsappNumber: '+971545566778',
    operatingHours: 'Sat-Thu: 07:00 - 16:30',
    tradeLicenseNumber: 'AJM-IN-2910',
    sourcePlatform: '2gis',
    sources: [
      { platform: '2gis', discoveredAt: '2026-09-18', lastVerifiedAt: '2026-10-24', isPrimary: true }
    ],
    dateDiscovered: '2026-09-18T13:40:00Z',
    dateLastVerified: '2026-10-24T11:20:00Z',
    qualityScore: 86,
    crmLeadStatus: 'unassigned'
  },
  {
    id: 'biz-rak-001',
    nameEn: 'RAK Ceramic & Granite Wholesale Supplies',
    nameAr: 'توريدات السيراميك والجرانيت بالجملة رأس الخيمة',
    normalizedName: 'rak ceramic granite wholesale supplies',
    category: 'Wholesale and trading companies',
    subcategory: 'Building Materials',
    description: 'Bulk distributor of premium porcelain, outdoor granite slabs, and sanitary fixtures supplying luxury villas and hotels.',
    emirate: 'Ras Al Khaimah',
    city: 'Ras Al Khaimah',
    area: 'Al Nakheel Commercial',
    streetAddress: 'Al Muntasir Road, Al Nakheel',
    buildingName: 'Al Nakheel Plaza, Suite 4',
    latitude: 25.7915,
    longitude: 55.9762,
    websiteUrl: 'https://rakceramicsupplies.ae',
    primaryPhone: '+971 7 228 3333',
    normalizedPhone: '+97172283333',
    primaryEmail: 'orders@rakceramicsupplies.ae',
    whatsappNumber: '+971502233445',
    operatingHours: 'Mon-Sat: 08:30 - 18:30',
    tradeLicenseNumber: 'RAK-TR-9941',
    sourcePlatform: 'google_places',
    sources: [
      { platform: 'google_places', discoveredAt: '2026-09-15', lastVerifiedAt: '2026-10-21', isPrimary: true }
    ],
    dateDiscovered: '2026-09-15T09:00:00Z',
    dateLastVerified: '2026-10-21T10:15:00Z',
    qualityScore: 88,
    crmLeadStatus: 'unassigned'
  },
  {
    id: 'biz-fuj-001',
    nameEn: 'Gulf Marine Bunkering & Vessel Services',
    nameAr: 'خدمات تزويد السفن والخدمات البحرية في الخليج',
    normalizedName: 'gulf marine bunkering vessel services',
    category: 'Logistics and transport',
    subcategory: 'Last-mile Delivery',
    description: 'Offshore ship chandlery, bunkering support, and technical vessel provisions positioned outside the Strait of Hormuz in Port of Fujairah.',
    emirate: 'Fujairah',
    city: 'Fujairah',
    area: 'Fujairah Oil Industry Zone (FOIZ)',
    streetAddress: 'Harbour Service Road, Marine Gate 3',
    buildingName: 'Fujairah Maritime Center',
    latitude: 25.1764,
    longitude: 56.3612,
    websiteUrl: 'https://gulfmarinefuj.com',
    primaryPhone: '+971 9 222 8111',
    normalizedPhone: '+97192228111',
    primaryEmail: 'ops@gulfmarinefuj.com',
    whatsappNumber: '+971508899001',
    operatingHours: '24/7 Operations',
    tradeLicenseNumber: 'FUJ-FZ-1420',
    sourcePlatform: 'google_places',
    sources: [
      { platform: 'google_places', discoveredAt: '2026-08-25', lastVerifiedAt: '2026-10-16', isPrimary: true }
    ],
    dateDiscovered: '2026-08-25T15:20:00Z',
    dateLastVerified: '2026-10-16T17:00:00Z',
    qualityScore: 93,
    crmLeadStatus: 'in_pipeline',
    crmLeadId: 'lead-006'
  },
  {
    id: 'biz-uaq-001',
    nameEn: 'Oasis Pure Bottled Water Manufacturing LLC',
    nameAr: 'مصنع مياه الواحة النقية ش.ذ.م.م',
    normalizedName: 'oasis pure bottled water manufacturing',
    category: 'Manufacturing and factories',
    subcategory: 'FMCG & Food Processing',
    description: 'Automated 5-gallon, PET bottle mineral water filling and bulk residential distribution facility.',
    emirate: 'Umm Al Quwain',
    city: 'Umm Al Quwain',
    area: 'UAQ Free Trade Zone',
    streetAddress: 'Industrial Sector 4, UAQ Free Zone',
    buildingName: 'Bottling Plant Unit B-1',
    latitude: 25.5342,
    longitude: 55.5528,
    websiteUrl: 'https://oasispureuaq.ae',
    primaryPhone: '+971 6 766 5000',
    normalizedPhone: '+97167665000',
    primaryEmail: 'distributors@oasispureuaq.ae',
    whatsappNumber: '+971554433221',
    operatingHours: 'Sun-Fri: 07:00 - 18:00',
    tradeLicenseNumber: 'UAQ-IN-6102',
    sourcePlatform: 'uae_yellowpages',
    sources: [
      { platform: 'uae_yellowpages', discoveredAt: '2026-09-08', lastVerifiedAt: '2026-10-14', isPrimary: true }
    ],
    dateDiscovered: '2026-09-08T08:30:00Z',
    dateLastVerified: '2026-10-14T09:45:00Z',
    qualityScore: 84,
    crmLeadStatus: 'unassigned'
  },
  {
    id: 'biz-dxb-004',
    nameEn: 'Al Futtaim Engineering & Technologies',
    nameAr: 'الفطيم للهندسة والتكنولوجيا',
    normalizedName: 'al futtaim engineering technologies',
    category: 'Construction and contracting',
    subcategory: 'MEP Engineering',
    description: 'Multi-disciplinary engineering solutions provider offering building products, HVAC, elevators, security systems, and energy management.',
    emirate: 'Dubai',
    city: 'Dubai',
    area: 'Business Bay',
    streetAddress: 'Al Saada Street, Business Bay',
    buildingName: 'Bay Square Building 6',
    latitude: 25.1872,
    longitude: 55.2789,
    websiteUrl: 'https://alfuttaim.com/engineering',
    primaryPhone: '+971 4 213 2222',
    normalizedPhone: '+97142132222',
    primaryEmail: 'inquiries.engineering@alfuttaim.com',
    whatsappNumber: '+971501239876',
    socialLinks: {
      linkedin: 'https://linkedin.com/company/al-futtaim-engineering'
    },
    operatingHours: 'Mon-Fri: 08:30 - 17:30',
    tradeLicenseNumber: 'DXB-CN-102938',
    sourcePlatform: 'google_places',
    sources: [
      { platform: 'google_places', discoveredAt: '2026-08-10', lastVerifiedAt: '2026-10-26', isPrimary: true },
      { platform: '2gis', discoveredAt: '2026-08-12', lastVerifiedAt: '2026-10-26' }
    ],
    dateDiscovered: '2026-08-10T10:00:00Z',
    dateLastVerified: '2026-10-26T14:00:00Z',
    qualityScore: 97,
    crmLeadStatus: 'in_pipeline',
    crmLeadId: 'lead-007'
  },
  {
    id: 'biz-dxb-dup-001',
    nameEn: 'Al-Futtaim Engineering LLC (Business Bay Branch)',
    nameAr: 'شركة الفطيم الهندسية ش.ذ.م.م - فرع الخليج التجاري',
    normalizedName: 'al futtaim engineering business bay branch',
    category: 'Construction and contracting',
    subcategory: 'MEP Engineering',
    description: 'Al Futtaim engineering branch office in Bay Square specializing in HVAC and facilities technology.',
    emirate: 'Dubai',
    city: 'Dubai',
    area: 'Business Bay',
    streetAddress: 'Bay Square Bldg 6, Floor 3, Business Bay',
    buildingName: 'Bay Square 6',
    latitude: 25.1875,
    longitude: 55.2792,
    websiteUrl: 'https://alfuttaim.com',
    primaryPhone: '+971 4 213 2222',
    normalizedPhone: '+97142132222',
    primaryEmail: 'info@alfuttaim.com',
    whatsappNumber: '+971501239876',
    operatingHours: 'Mon-Fri: 08:30 - 17:30',
    tradeLicenseNumber: 'DXB-CN-102938-1',
    sourcePlatform: '2gis',
    sources: [
      { platform: '2gis', discoveredAt: '2026-10-01', lastVerifiedAt: '2026-10-20', isPrimary: true }
    ],
    dateDiscovered: '2026-10-01T11:00:00Z',
    dateLastVerified: '2026-10-20T16:00:00Z',
    qualityScore: 88,
    crmLeadStatus: 'unassigned'
  },
  {
    id: 'biz-dxb-005',
    nameEn: 'Zuma Dubai Contemporary Japanese Restaurant',
    nameAr: 'زوما دبي مطعم ياباني معاصر',
    normalizedName: 'zuma dubai restaurant',
    category: 'Restaurants and cafes',
    subcategory: 'Fine Dining',
    description: 'World-renowned izakaya style fine dining and cocktail lounge located in the financial heart of Dubai DIFC.',
    emirate: 'Dubai',
    city: 'Dubai',
    area: 'DIFC',
    streetAddress: 'Podium Level, Gate Village 06, DIFC',
    buildingName: 'Gate Village 06',
    latitude: 25.2134,
    longitude: 55.2821,
    websiteUrl: 'https://zumarestaurant.com/locations/dubai',
    primaryPhone: '+971 4 425 5660',
    normalizedPhone: '+97144255660',
    primaryEmail: 'info@zumarestaurant.ae',
    whatsappNumber: '+971529900112',
    socialLinks: {
      instagram: 'https://instagram.com/zumadubai'
    },
    operatingHours: 'Daily: 12:00 - 02:00',
    tradeLicenseNumber: 'DIFC-CL-4890',
    sourcePlatform: 'google_places',
    sources: [
      { platform: 'google_places', discoveredAt: '2026-08-01', lastVerifiedAt: '2026-10-24', isPrimary: true }
    ],
    dateDiscovered: '2026-08-01T09:00:00Z',
    dateLastVerified: '2026-10-24T18:00:00Z',
    qualityScore: 99,
    crmLeadStatus: 'customer'
  },
  {
    id: 'biz-auh-003',
    nameEn: 'Hub71 Global Tech Ecosystem',
    nameAr: 'منظومة هاب 71 العالمية للتكنولوجيا',
    normalizedName: 'hub71 global tech ecosystem',
    category: 'IT and software companies',
    subcategory: 'Enterprise SaaS',
    description: 'Abu Dhabi global tech community backed by Mubadala uniting founders, investors, and enterprise tech partners.',
    emirate: 'Abu Dhabi',
    city: 'Abu Dhabi',
    area: 'Al Maryah Island (ADGM)',
    streetAddress: 'Al Khatem Tower, Floors 14-16, ADGM Square',
    buildingName: 'Al Khatem Tower',
    latitude: 24.5028,
    longitude: 54.3888,
    websiteUrl: 'https://hub71.com',
    primaryPhone: '+971 2 610 8888',
    normalizedPhone: '+97126108888',
    primaryEmail: 'partnerships@hub71.com',
    whatsappNumber: '+971509911223',
    socialLinks: {
      linkedin: 'https://linkedin.com/company/hub71',
      twitter: 'https://twitter.com/hub71ad'
    },
    operatingHours: 'Sun-Thu: 08:00 - 18:00',
    tradeLicenseNumber: 'ADGM-FZE-0012',
    sourcePlatform: 'web_crawl',
    sources: [
      { platform: 'web_crawl', discoveredAt: '2026-08-18', lastVerifiedAt: '2026-10-25', isPrimary: true },
      { platform: 'google_places', discoveredAt: '2026-08-19', lastVerifiedAt: '2026-10-25' }
    ],
    dateDiscovered: '2026-08-18T10:00:00Z',
    dateLastVerified: '2026-10-25T11:00:00Z',
    qualityScore: 98,
    crmLeadStatus: 'in_pipeline',
    crmLeadId: 'lead-008'
  }
];

export const INITIAL_DUPLICATES: DuplicateCandidate[] = [
  {
    id: 'dup-001',
    primaryBusinessId: 'biz-dxb-004',
    secondaryBusinessId: 'biz-dxb-dup-001',
    primaryName: 'Al Futtaim Engineering & Technologies',
    secondaryName: 'Al-Futtaim Engineering LLC (Business Bay Branch)',
    confidenceScore: 94.2,
    matchCriteria: {
      nameSimilarity: 92.5,
      phoneMatch: true,
      domainMatch: true,
      geoDistanceMeters: 45
    },
    status: 'pending'
  }
];

export const INITIAL_TEAM: TeamMember[] = [
  {
    id: 'usr-1',
    name: 'Tariq Al Hashemi',
    email: 'tariq.hashemi@al-mirsaad.ae',
    role: 'sales_manager',
    avatar: 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=256&q=80',
    leadsAssigned: 18,
    pipelineValueAed: 1450000,
    dealsWonAed: 620000,
    quotaProgress: 88
  },
  {
    id: 'usr-2',
    name: 'Sara Bin Dhaen',
    email: 'sara.dhaen@al-mirsaad.ae',
    role: 'account_executive',
    avatar: 'https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?auto=format&fit=crop&w=256&q=80',
    leadsAssigned: 24,
    pipelineValueAed: 1980000,
    dealsWonAed: 890000,
    quotaProgress: 112
  },
  {
    id: 'usr-3',
    name: 'Omar Mansoor',
    email: 'omar.mansoor@al-mirsaad.ae',
    role: 'sdr',
    avatar: 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&w=256&q=80',
    leadsAssigned: 32,
    pipelineValueAed: 820000,
    dealsWonAed: 240000,
    quotaProgress: 74
  },
  {
    id: 'usr-4',
    name: 'Layla Al Qasimi',
    email: 'layla.qasimi@al-mirsaad.ae',
    role: 'account_executive',
    avatar: 'https://images.unsplash.com/photo-1580489944761-15a19d654956?auto=format&fit=crop&w=256&q=80',
    leadsAssigned: 19,
    pipelineValueAed: 1620000,
    dealsWonAed: 530000,
    quotaProgress: 95
  }
];

export const INITIAL_LEADS: CrmLead[] = [
  {
    id: 'lead-001',
    businessId: 'biz-dxb-001',
    businessName: 'Al Naboodah Construction Group LLC',
    category: 'Construction and contracting',
    emirate: 'Dubai',
    area: 'Al Quoz Industrial',
    assignedUserId: 'usr-1',
    assignedUserName: 'Tariq Al Hashemi',
    pipelineStage: 'proposal_sent',
    dealValueAed: 280000,
    expectedCloseDate: '2026-11-20',
    priority: 'urgent',
    tags: ['Tier 1 Contractor', 'Infrastructure', 'Annual Enterprise'],
    aiSummary: 'Conglomerate contractor managing road & infrastructure projects in Dubai & Sharjah. High purchase power for heavy machinery tracking & ERP modules.',
    aiPitchEn: 'Dear Al Naboodah Project Directors, noticing your major new highway works in Al Quoz, our enterprise fleet telematics and predictive maintenance platform can cut your equipment downtime by 24% while satisfying Dubai RTA compliance standards.',
    aiPitchAr: 'السادة مدراء المشاريع في مجموعة النابودة للمقاولات، بالنظر لمشاريعكم البنيوية الضخمة، توفر منصتنا حلولاً فورية لإدارة الآليات وخفض تكاليف الصيانة بنسبة 24% مع الامتثال الكامل لمعايير هيئة الطرق والمواصلات.',
    tasks: [
      {
        id: 'tsk-001',
        leadId: 'lead-001',
        title: 'Review revised SLA with Head of Procurement',
        dueDate: '2026-10-30',
        status: 'pending',
        priority: 'urgent',
        assignedUserName: 'Tariq Al Hashemi'
      }
    ],
    activities: [
      {
        id: 'act-001',
        leadId: 'lead-001',
        type: 'meeting',
        summary: 'Demoed enterprise analytics dashboard to VP Procurement',
        details: 'Client requested specific pricing for 150 fleet vehicles.',
        timestamp: '2026-10-24T14:00:00Z',
        authorName: 'Tariq Al Hashemi'
      }
    ],
    contacts: [
      {
        id: 'con-001',
        leadId: 'lead-001',
        businessId: 'biz-dxb-001',
        businessName: 'Al Naboodah Construction Group LLC',
        fullName: 'Rashid Al Naboodah',
        jobTitle: 'Director of Procurement & Supply Chain',
        email: 'r.naboodah@alnaboodahconstruction.com',
        phone: '+971 4 294 8888',
        whatsapp: '+971509876543',
        isPrimary: true
      }
    ],
    createdAt: '2026-08-16T10:00:00Z',
    updatedAt: '2026-10-24T14:00:00Z'
  },
  {
    id: 'lead-002',
    businessId: 'biz-dxb-002',
    businessName: 'Espace Real Estate Brokerage',
    category: 'Real estate',
    emirate: 'Dubai',
    area: 'Dubai Marina',
    assignedUserId: 'usr-2',
    assignedUserName: 'Sara Bin Dhaen',
    pipelineStage: 'meeting_scheduled',
    dealValueAed: 120000,
    expectedCloseDate: '2026-11-15',
    priority: 'high',
    tags: ['Luxury Brokerage', 'CRM Migration', 'Dubai Marina'],
    aiSummary: 'High-volume luxury real estate agency in Marina Plaza looking for automated buyer-investor matching and WhatsApp lead distribution.',
    aiPitchEn: 'Dear Espace Commercial Team, we noticed your expanding Palm Jumeirah and Marina portfolio. Our automated UAE B2B lead enrichment instantly matches high-net-worth investor profiles to your listings with automated WhatsApp alerts.',
    aiPitchAr: 'فريق إسباس العقاري، يسعدنا تزويد مستشاريكم العقاريين بنظام ذكاء اصطناعي يربط فئات المستثمرين الخليجيين والدوليين بوحداتكم الفاخرة عبر تنبيهات الواتساب الفورية.',
    tasks: [
      {
        id: 'tsk-002',
        leadId: 'lead-002',
        title: 'Virtual Walkthrough with Managing Director',
        dueDate: '2026-11-02',
        status: 'pending',
        priority: 'high',
        assignedUserName: 'Sara Bin Dhaen'
      }
    ],
    activities: [
      {
        id: 'act-002',
        leadId: 'lead-002',
        type: 'call',
        summary: 'Discovery call with Head of Sales',
        details: 'Interested in WhatsApp integration and RERA compliance data.',
        timestamp: '2026-10-22T11:30:00Z',
        authorName: 'Sara Bin Dhaen'
      }
    ],
    contacts: [
      {
        id: 'con-002',
        leadId: 'lead-002',
        businessId: 'biz-dxb-002',
        businessName: 'Espace Real Estate Brokerage',
        fullName: 'Roland E.',
        jobTitle: 'Managing Director',
        email: 'roland@espace.ae',
        phone: '+971 4 306 9999',
        whatsapp: '+971521234567',
        isPrimary: true
      }
    ],
    createdAt: '2026-09-02T11:00:00Z',
    updatedAt: '2026-10-22T11:30:00Z'
  },
  {
    id: 'lead-003',
    businessId: 'biz-dxb-003',
    businessName: 'Apex Cloud Solutions FZ-LLC',
    category: 'IT and software companies',
    emirate: 'Dubai',
    area: 'Dubai Silicon Oasis',
    assignedUserId: 'usr-3',
    assignedUserName: 'Omar Mansoor',
    pipelineStage: 'qualified',
    dealValueAed: 185000,
    expectedCloseDate: '2026-12-05',
    priority: 'medium',
    tags: ['Tech Partner', 'Cybersecurity', 'DSO'],
    tasks: [],
    activities: [],
    contacts: [
      {
        id: 'con-003',
        leadId: 'lead-003',
        businessId: 'biz-dxb-003',
        businessName: 'Apex Cloud Solutions FZ-LLC',
        fullName: 'Kareem Farouq',
        jobTitle: 'Chief Technology Officer',
        email: 'kareem@apexcloud.ae',
        phone: '+971 4 501 5555',
        whatsapp: '+971556789012',
        isPrimary: true
      }
    ],
    createdAt: '2026-09-14T09:00:00Z',
    updatedAt: '2026-10-18T10:00:00Z'
  },
  {
    id: 'lead-004',
    businessId: 'biz-auh-001',
    businessName: 'Al Faraa Integrated Construction Group',
    category: 'Construction and contracting',
    emirate: 'Abu Dhabi',
    area: 'Musaffah Industrial',
    assignedUserId: 'usr-4',
    assignedUserName: 'Layla Al Qasimi',
    pipelineStage: 'contacted',
    dealValueAed: 350000,
    expectedCloseDate: '2026-12-20',
    priority: 'high',
    tags: ['Abu Dhabi Gov Projects', 'Musaffah'],
    tasks: [
      {
        id: 'tsk-003',
        leadId: 'lead-004',
        title: 'Send customized UAE compliance whitepaper',
        dueDate: '2026-11-04',
        status: 'pending',
        priority: 'medium',
        assignedUserName: 'Layla Al Qasimi'
      }
    ],
    activities: [],
    contacts: [
      {
        id: 'con-004',
        leadId: 'lead-004',
        businessId: 'biz-auh-001',
        businessName: 'Al Faraa Integrated Construction Group',
        fullName: 'Eng. Salem Al Faraa',
        jobTitle: 'Executive Vice President',
        email: 'salem@alfaraagroup.com',
        phone: '+971 2 551 2222',
        whatsapp: '+971503344556',
        isPrimary: true
      }
    ],
    createdAt: '2026-08-22T14:00:00Z',
    updatedAt: '2026-10-19T08:00:00Z'
  },
  {
    id: 'lead-005',
    businessId: 'biz-shj-001',
    businessName: 'Sharjah Freight Line Logistics LLC',
    category: 'Logistics and transport',
    emirate: 'Sharjah',
    area: 'SAIF Zone',
    assignedUserId: 'usr-2',
    assignedUserName: 'Sara Bin Dhaen',
    pipelineStage: 'negotiation',
    dealValueAed: 95000,
    expectedCloseDate: '2026-11-10',
    priority: 'urgent',
    tags: ['Air Freight', 'SAIF Free Zone', 'Bonded Storage'],
    tasks: [],
    activities: [],
    contacts: [
      {
        id: 'con-005',
        leadId: 'lead-005',
        businessId: 'biz-shj-001',
        businessName: 'Sharjah Freight Line Logistics LLC',
        fullName: 'Capt. Mansoor Al Qasimi',
        jobTitle: 'Managing Partner',
        email: 'mansoor@shjfreight.com',
        phone: '+971 6 557 4444',
        whatsapp: '+971569988771',
        isPrimary: true
      }
    ],
    createdAt: '2026-09-12T15:00:00Z',
    updatedAt: '2026-10-24T16:00:00Z'
  },
  {
    id: 'lead-006',
    businessId: 'biz-fuj-001',
    businessName: 'Gulf Marine Bunkering & Vessel Services',
    category: 'Logistics and transport',
    emirate: 'Fujairah',
    area: 'Fujairah Oil Industry Zone (FOIZ)',
    assignedUserId: 'usr-1',
    assignedUserName: 'Tariq Al Hashemi',
    pipelineStage: 'new_lead',
    dealValueAed: 140000,
    expectedCloseDate: '2026-12-15',
    priority: 'medium',
    tags: ['Maritime Services', 'Fujairah Port'],
    tasks: [],
    activities: [],
    contacts: [],
    createdAt: '2026-08-26T11:00:00Z',
    updatedAt: '2026-10-17T11:00:00Z'
  },
  {
    id: 'lead-007',
    businessId: 'biz-dxb-004',
    businessName: 'Al Futtaim Engineering & Technologies',
    category: 'Construction and contracting',
    emirate: 'Dubai',
    area: 'Business Bay',
    assignedUserId: 'usr-4',
    assignedUserName: 'Layla Al Qasimi',
    pipelineStage: 'meeting_scheduled',
    dealValueAed: 420000,
    expectedCloseDate: '2026-11-28',
    priority: 'urgent',
    tags: ['Enterprise Conglomerate', 'Smart Building IoT'],
    tasks: [],
    activities: [],
    contacts: [],
    createdAt: '2026-08-11T12:00:00Z',
    updatedAt: '2026-10-26T15:00:00Z'
  },
  {
    id: 'lead-008',
    businessId: 'biz-auh-003',
    businessName: 'Hub71 Global Tech Ecosystem',
    category: 'IT and software companies',
    emirate: 'Abu Dhabi',
    area: 'Al Maryah Island (ADGM)',
    assignedUserId: 'usr-2',
    assignedUserName: 'Sara Bin Dhaen',
    pipelineStage: 'won',
    dealValueAed: 260000,
    expectedCloseDate: '2026-10-15',
    priority: 'high',
    tags: ['SaaS Ecosystem Partner', 'ADGM Freezone'],
    tasks: [],
    activities: [],
    contacts: [],
    createdAt: '2026-08-20T10:00:00Z',
    updatedAt: '2026-10-15T18:00:00Z'
  }
];

export const INITIAL_COLLECTION_JOBS: CollectionJob[] = [
  {
    id: 'job-101',
    sourcePlatform: 'google_places',
    emirate: 'Dubai',
    area: 'Business Bay',
    category: 'Real estate',
    searchQuery: 'Real estate developers and agencies in Business Bay',
    status: 'completed',
    recordsDiscovered: 84,
    duplicatesDetected: 12,
    newRecordsAdded: 72,
    startedAt: '2026-10-26T08:00:00Z',
    completedAt: '2026-10-26T08:04:12Z',
    logs: [
      'Initialized Google Places API client with UAE boundary box',
      'Searching grid tiles around Business Bay (25.1872, 55.2789)',
      'Extracted 84 raw Place Details records',
      'Applied UAE E.164 phone normalizer: 82 phones standardized',
      'Fuzzy deduplication engine identified 12 duplicate candidates',
      'Stored 72 golden records with 30-day cache expiry markers',
      'Job completed in 4m 12s with 0 errors'
    ]
  },
  {
    id: 'job-102',
    sourcePlatform: '2gis',
    emirate: 'Abu Dhabi',
    area: 'Musaffah Industrial',
    category: 'Construction and contracting',
    searchQuery: 'Building materials and MEP contractors in Musaffah',
    status: 'completed',
    recordsDiscovered: 65,
    duplicatesDetected: 8,
    newRecordsAdded: 57,
    startedAt: '2026-10-25T14:15:00Z',
    completedAt: '2026-10-25T14:19:40Z',
    logs: [
      'Connected to 2GIS UAE catalog service endpoint',
      'Queried sector M-1 to M-40 in Musaffah Industrial Area',
      '65 commercial establishments retrieved with entrance coordinates',
      'Extracted verified landline and WhatsApp business contacts',
      'Merged with existing Abu Dhabi DED license registry',
      'Completed successfully'
    ]
  },
  {
    id: 'job-103',
    sourcePlatform: 'uae_yellowpages',
    emirate: 'Sharjah',
    area: 'Sharjah Industrial Area',
    category: 'Automobile services',
    searchQuery: 'Commercial auto garages and fleet workshops',
    status: 'completed',
    recordsDiscovered: 48,
    duplicatesDetected: 5,
    newRecordsAdded: 43,
    startedAt: '2026-10-24T11:00:00Z',
    completedAt: '2026-10-24T11:03:15Z',
    logs: [
      'Ingested permitted public commercial directory feed',
      'Validated UAE Trade Licenses against Ministry of Economy records',
      'Saved 43 new verified records'
    ]
  }
];

export const INITIAL_SUPPRESSIONS: SuppressionRecord[] = [
  {
    id: 'sup-1',
    type: 'phone',
    value: '+97143999999',
    reason: 'Executive requested opt-out under UAE PDPL Article 12',
    dateAdded: '2026-09-10'
  },
  {
    id: 'sup-2',
    type: 'email',
    value: 'director.general@private-family-office.ae',
    reason: 'Do-not-solicit notice recorded',
    dateAdded: '2026-09-18'
  },
  {
    id: 'sup-3',
    type: 'domain',
    value: 'defense-uae-classified.ae',
    reason: 'Government defense entity exclusion',
    dateAdded: '2026-08-01'
  }
];

export const INITIAL_AUDIT_LOGS: AuditLog[] = [
  {
    id: 'log-001',
    action: 'LEAD_CONVERTED',
    userId: 'usr-1',
    userName: 'Tariq Al Hashemi',
    resourceType: 'CRM_LEAD',
    details: 'Converted "Al Naboodah Construction Group LLC" to CRM Lead (AED 280,000)',
    timestamp: '2026-10-26T10:14:00Z'
  },
  {
    id: 'log-002',
    action: 'DUPLICATE_MERGED',
    userId: 'usr-2',
    userName: 'Sara Bin Dhaen',
    resourceType: 'BUSINESS',
    details: 'Auto-merged 12 duplicate records discovered during Business Bay collection job',
    timestamp: '2026-10-26T08:05:00Z'
  },
  {
    id: 'log-003',
    action: 'COMPLIANCE_SUPPRESSION_CHECKED',
    userId: 'usr-3',
    userName: 'Omar Mansoor',
    resourceType: 'EXPORT_ENGINE',
    details: 'Validated 45 records against UAE TDRA suppression list prior to CSV export',
    timestamp: '2026-10-25T16:22:00Z'
  }
];
