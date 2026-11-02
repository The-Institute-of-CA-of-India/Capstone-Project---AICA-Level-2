const fs = require('fs');
const path = require('path');

const RAW_FILE = path.join(__dirname, '..', 'public', 'assets', 'aistudio', 'UAE_Gold_Directory_ALL_2026-10-25_eb5c5718.json');
const DB_FILE = path.join(__dirname, '..', 'data', 'uae_database.json');

function normalizeString(str) {
  return (str || '')
    .toLowerCase()
    .replace(/[^\w\s]/gi, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function normalizeUaePhone(phone) {
  if (!phone || phone === 'Not Available') return '';
  const digits = phone.replace(/[^\d]/g, '');
  if (digits.startsWith('971')) return `+${digits}`;
  if (digits.startsWith('0')) return `+971${digits.slice(1)}`;
  if (digits.length === 9) return `+971${digits}`;
  return `+${digits}`;
}

function calculateStringSimilarity(s1, s2) {
  const longer = s1.length > s2.length ? s1 : s2;
  const shorter = s1.length > s2.length ? s2 : s1;
  const longerLength = longer.length;
  if (longerLength === 0) return 1.0;
  
  const costs = [];
  for (let i = 0; i <= longer.length; i++) {
    let lastValue = i;
    for (let j = 0; j <= shorter.length; j++) {
      if (i === 0) costs[j] = j;
      else if (j > 0) {
        let newValue = costs[j - 1];
        if (longer.charAt(i - 1) !== shorter.charAt(j - 1)) {
          newValue = Math.min(Math.min(newValue, lastValue), costs[j]) + 1;
        }
        costs[j - 1] = lastValue;
        lastValue = newValue;
      }
    }
    if (i > 0) costs[shorter.length] = lastValue;
  }
  return (longerLength - costs[shorter.length]) / longerLength;
}

const AREA_COORDS = {
  'Dubai Gold Souk': { lat: 25.2685, lng: 55.2974 },
  'Deira': { lat: 25.2690, lng: 55.3010 },
  'DMCC': { lat: 25.0745, lng: 55.1455 },
  'JLT': { lat: 25.0745, lng: 55.1455 },
  'Gold & Diamond Park': { lat: 25.1278, lng: 55.2065 },
  'Al Quoz': { lat: 25.1320, lng: 55.2340 },
  'Business Bay': { lat: 25.1855, lng: 55.2755 },
  'Meena Bazaar': { lat: 25.2605, lng: 55.2950 },
  'Bur Dubai': { lat: 25.2580, lng: 55.2980 },
  'Madinat Zayed': { lat: 24.4820, lng: 54.3680 },
  'Central Souk': { lat: 25.3485, lng: 55.3880 },
  'Rolla': { lat: 25.3560, lng: 55.3890 },
  'SAIF Zone': { lat: 25.3280, lng: 55.5180 },
  'Sharjah': { lat: 25.3573, lng: 55.4033 },
  'Abu Dhabi': { lat: 24.4539, lng: 54.3773 },
  'Ajman': { lat: 25.4050, lng: 55.5130 },
  'Ras Al Khaimah': { lat: 25.7890, lng: 55.9430 },
  'Fujairah': { lat: 25.1280, lng: 56.3260 },
  'Umm Al Quwain': { lat: 25.5650, lng: 55.5530 }
};

function getCoordsForArea(area, emirate) {
  let base = null;
  if (area) {
    for (const [key, coords] of Object.entries(AREA_COORDS)) {
      if (area.toLowerCase().includes(key.toLowerCase())) {
        base = coords;
        break;
      }
    }
  }
  if (!base && emirate) {
    base = AREA_COORDS[emirate];
  }
  if (!base) {
    base = { lat: 25.2685, lng: 55.2974 };
  }
  // add micro-jitter so multiple shops in the souk have distinct pin locations
  const jitterLat = (Math.random() - 0.5) * 0.008;
  const jitterLng = (Math.random() - 0.5) * 0.008;
  return {
    lat: +(base.lat + jitterLat).toFixed(6),
    lng: +(base.lng + jitterLng).toFixed(6)
  };
}

function extractEntrance(addr) {
  if (!addr) return undefined;
  const match = addr.match(/(Gate\s*(?:No\.?)?\s*[\dA-Z]+|Shop\s*(?:No\.?)?\s*[\w\d\-\/]+|Cluster\s*[A-Z]|Building\s*[\dA-Z]+|Floor\s*[\dA-Z]+|Level\s*[\dA-Z]+|Office\s*[\dA-Z]+)/i);
  return match ? match[0] : undefined;
}

function runIngestion() {
  console.log('Loading raw gold directory from:', RAW_FILE);
  const rawData = JSON.parse(fs.readFileSync(RAW_FILE, 'utf8'));
  console.log(`Loaded ${rawData.length} items from Gold Directory.`);

  const db = JSON.parse(fs.readFileSync(DB_FILE, 'utf8'));
  console.log(`Current DB contains ${db.businesses.length} businesses.`);

  let newlyAdded = 0;
  let enriched = 0;

  for (const item of rawData) {
    const name = item['Company Name'];
    if (!name) continue;

    const norm = normalizeString(name);
    const existing = db.businesses.find(b => {
      if (calculateStringSimilarity(b.normalizedName, norm) > 0.86) return true;
      if (item['Telephone'] && item['Telephone'] !== 'Not Available') {
        const pNorm = normalizeUaePhone(item['Telephone']);
        if (pNorm && b.normalizedPhone === pNorm) return true;
      }
      return false;
    });

    const phone = item['Telephone'] !== 'Not Available' ? item['Telephone'] : (item['Mobile'] !== 'Not Available' ? item['Mobile'] : undefined);
    const mobile = item['Mobile'] !== 'Not Available' ? item['Mobile'] : undefined;
    const whatsapp = item['WhatsApp'] !== 'Not Available' ? item['WhatsApp'] : mobile;
    const email = item['Email'] !== 'Not Available' ? item['Email'] : undefined;
    const website = item['Website'] !== 'Not Available' ? item['Website'] : undefined;
    const emirate = item['Emirate'] || 'Dubai';
    const area = item['Area'] || 'Dubai Gold Souk';
    const coords = getCoordsForArea(area, emirate);
    const entrance = extractEntrance(item['Business Address']);

    // Social links
    const socialLinks = {};
    if (item['LinkedIn'] && item['LinkedIn'] !== 'Not Available') {
      socialLinks.linkedin = item['LinkedIn'];
    }
    if (item['Other Social Media'] && item['Other Social Media'] !== 'Not Available') {
      const matchInsta = item['Other Social Media'].match(/Instagram:\s*(@[\w\d_\.]+)/i);
      if (matchInsta) socialLinks.instagram = `https://instagram.com/${matchInsta[1].replace('@', '')}`;
    }

    // Quality Score
    let score = 70;
    if (phone) score += 8;
    if (email) score += 8;
    if (website) score += 6;
    if (whatsapp) score += 4;
    if (item['Verification Status'] === 'Verified') score += 4;

    const sourceRecord = {
      platform: (item['Source'] || '').includes('Google') ? 'google_places' : 'ded_registry',
      sourceUrl: item['Source URL'] !== 'Not Available' ? item['Source URL'] : undefined,
      discoveredAt: item['Last Verified Date'] ? `${item['Last Verified Date']}T00:00:00.000Z` : new Date().toISOString(),
      lastVerifiedAt: item['Last Verified Date'] ? `${item['Last Verified Date']}T00:00:00.000Z` : new Date().toISOString(),
      isPrimary: true
    };

    if (existing) {
      enriched++;
      existing.twoGisListingUrl = existing.twoGisListingUrl || (item['Website'] !== 'Not Available' ? item['Website'] : undefined);
      existing.buildingEntrance = existing.buildingEntrance || entrance;
      if (email && !existing.primaryEmail) existing.primaryEmail = email;
      if (whatsapp && !existing.whatsappNumber) existing.whatsappNumber = whatsapp;
      if (phone && !existing.primaryPhone) {
        existing.primaryPhone = phone;
        existing.normalizedPhone = normalizeUaePhone(phone);
      }
      existing.qualityScore = Math.max(existing.qualityScore, score);
    } else {
      newlyAdded++;
      const newBiz = {
        id: `biz-gold-${item['Serial Number'] || newlyAdded}`,
        nameEn: name,
        nameAr: /[\u0600-\u06FF]/.test(name) ? name : `شركة ${name.split(' ')[0]} للذهب والمجوهرات`,
        normalizedName: norm,
        category: 'Gold, Jewellery & Precious Metals',
        subcategory: item['Business Category'] || 'Gold jewellery retailers',
        description: `${item['Business Activity'] || 'Precious metals and fine gold trading'}. ${item['Remarks'] || ''}`.trim(),
        emirate: emirate,
        city: emirate,
        area: area,
        streetAddress: item['Business Address'] || `${area}, ${emirate}`,
        buildingName: item['Business Address'] ? item['Business Address'].split('-')[0].trim() : undefined,
        buildingEntrance: entrance,
        plotNumber: item['Mainland / Free Zone'] ? `${item['Mainland / Free Zone']} (${item['Registration Authority'] || 'DED'})` : undefined,
        googleMapsListingUrl: `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${name} ${area} ${emirate}`)}`,
        twoGisListingUrl: item['Website'] !== 'Not Available' ? item['Website'] : undefined,
        latitude: coords.lat,
        longitude: coords.lng,
        websiteUrl: website,
        primaryPhone: phone,
        normalizedPhone: normalizeUaePhone(phone || ''),
        primaryEmail: email,
        whatsappNumber: whatsapp,
        socialLinks: Object.keys(socialLinks).length > 0 ? socialLinks : undefined,
        operatingHours: 'Mon - Sat: 09:30 - 22:00, Fri: 16:00 - 22:00',
        tradeLicenseNumber: item['Registration Authority'] || 'DET-Gold-Trade',
        sourcePlatform: sourceRecord.platform,
        sources: [sourceRecord],
        dateDiscovered: sourceRecord.discoveredAt,
        dateLastVerified: sourceRecord.lastVerifiedAt,
        qualityScore: Math.min(score, 100),
        crmLeadStatus: 'unassigned'
      };

      db.businesses.push(newBiz);
    }
  }

  // Ensure category exists
  let goldCat = db.categories.find(c => c.nameEn === 'Gold, Jewellery & Precious Metals');
  const goldSubcats = [
    'Gold refineries',
    'Gold jewellery retailers',
    'Gold jewellery wholesalers',
    'Gold bullion dealers',
    'Gold jewellery manufacturers',
    'Gold trading companies',
    'Precious stones dealers',
    'Diamond trading companies'
  ];

  if (!goldCat) {
    goldCat = {
      id: 'cat-gold-precious-metals',
      nameEn: 'Gold, Jewellery & Precious Metals',
      nameAr: 'الذهب والمجوهرات والمعادن الثمينة',
      slug: 'gold-jewellery-precious-metals',
      icon: 'Gem',
      businessCount: newlyAdded + enriched,
      subcategories: goldSubcats
    };
    db.categories.unshift(goldCat);
  } else {
    goldCat.subcategories = Array.from(new Set([...goldCat.subcategories, ...goldSubcats]));
    goldCat.businessCount = (goldCat.businessCount || 0) + newlyAdded;
  }

  // Add audit log
  db.auditLogs.unshift({
    id: `log-gold-${Date.now()}`,
    action: 'DATASET_INGESTED_UAE_GOLD_DIRECTORY',
    userId: 'usr-admin',
    userName: 'Admin User (admin@sa-auditors.com)',
    resourceType: 'BUSINESS_DATABASE',
    resourceId: 'uae-gold-directory-2026',
    details: `Successfully ingested UAE Gold Directory dataset. Total records processed: ${rawData.length} | Newly added: +${newlyAdded} | Enriched existing: ${enriched}. Total database now: ${db.businesses.length} businesses.`,
    timestamp: new Date().toISOString()
  });

  console.log(`\n=== INGESTION FINISHED ===`);
  console.log(`Processed: ${rawData.length}`);
  console.log(`Newly Added: +${newlyAdded}`);
  console.log(`Enriched existing: ${enriched}`);
  console.log(`Total businesses now in DB: ${db.businesses.length}`);

  fs.writeFileSync(DB_FILE, JSON.stringify(db, null, 2), 'utf8');
  console.log(`Successfully saved to ${DB_FILE}`);
}

runIngestion();
