// Static product catalog for the AI Workspace hero visualization.
// 10 real products spanning multiple categories.

export interface ProductSpec {
  label: string;
  value: string;
  status: 'passed' | 'warning';
}

export interface HolographicProduct {
  id: string;
  name: string;
  category: 'laptop' | 'phone' | 'monitor' | 'tablet' | 'headphones';
  score: number;
  price: string;
  icon: string;
  specs: ProductSpec[];
  tags: string[];
}

export const PRODUCT_CATALOG: HolographicProduct[] = [
  {
    id: 'nitro-v15',
    name: 'Nitro V 15',
    category: 'laptop',
    score: 94,
    price: '₹78,400',
    icon: '💻',
    specs: [
      { label: 'GPU', value: 'RTX 4060', status: 'passed' },
      { label: 'RAM', value: '16GB DDR5', status: 'passed' },
      { label: 'Display', value: '144Hz IPS', status: 'passed' },
      { label: 'Storage', value: '512GB SSD', status: 'passed' },
    ],
    tags: ['RTX 4060', 'Gaming', '144Hz', 'Best Value'],
  },
  {
    id: 'rog-g14',
    name: 'ROG Zephyrus G14',
    category: 'laptop',
    score: 91,
    price: '₹1,49,990',
    icon: '💻',
    specs: [
      { label: 'GPU', value: 'RTX 4070', status: 'passed' },
      { label: 'RAM', value: '32GB DDR5', status: 'passed' },
      { label: 'Display', value: '120Hz OLED', status: 'passed' },
      { label: 'Weight', value: '1.72 kg', status: 'warning' },
    ],
    tags: ['RTX 4070', 'OLED', 'Creator', 'Premium'],
  },
  {
    id: 'macbook-air-m3',
    name: 'MacBook Air M3',
    category: 'laptop',
    score: 88,
    price: '₹1,14,900',
    icon: '💻',
    specs: [
      { label: 'Chip', value: 'Apple M3', status: 'passed' },
      { label: 'RAM', value: '16GB Unified', status: 'passed' },
      { label: 'Display', value: 'Liquid Retina', status: 'passed' },
      { label: 'Battery', value: '18 Hours', status: 'passed' },
    ],
    tags: ['Apple M3', 'Battery 18hr', 'Fanless', 'Verified'],
  },
  {
    id: 'nothing-phone-2a',
    name: 'Nothing Phone 2a',
    category: 'phone',
    score: 91,
    price: '₹23,999',
    icon: '📱',
    specs: [
      { label: 'Screen', value: 'OLED 120Hz', status: 'passed' },
      { label: 'Camera', value: '50MP Dual', status: 'passed' },
      { label: 'Battery', value: '5000 mAh', status: 'passed' },
      { label: 'Charging', value: '45W', status: 'warning' },
    ],
    tags: ['OLED', '120Hz', '5000mAh', 'AI Pick'],
  },
  {
    id: 'galaxy-s24-ultra',
    name: 'Galaxy S24 Ultra',
    category: 'phone',
    score: 96,
    price: '₹1,29,999',
    icon: '📱',
    specs: [
      { label: 'Screen', value: 'AMOLED 120Hz', status: 'passed' },
      { label: 'Camera', value: '200MP Quad', status: 'passed' },
      { label: 'AI', value: 'Galaxy AI', status: 'passed' },
      { label: 'S-Pen', value: 'Included', status: 'passed' },
    ],
    tags: ['200MP', 'S-Pen', 'Galaxy AI', 'Top Rated'],
  },
  {
    id: 'dell-ultrasharp-27',
    name: 'Dell UltraSharp 27',
    category: 'monitor',
    score: 93,
    price: '₹42,500',
    icon: '🖥️',
    specs: [
      { label: 'Panel', value: '4K IPS', status: 'passed' },
      { label: 'Color', value: '100% sRGB', status: 'passed' },
      { label: 'Port', value: 'USB-C 90W', status: 'passed' },
      { label: 'Refresh', value: '60Hz', status: 'warning' },
    ],
    tags: ['4K', 'USB-C', 'IPS', 'Creator'],
  },
  {
    id: 'lg-oled-27',
    name: 'LG UltraGear OLED',
    category: 'monitor',
    score: 96,
    price: '₹59,999',
    icon: '🖥️',
    specs: [
      { label: 'Panel', value: '4K OLED', status: 'passed' },
      { label: 'HDR', value: 'HDR10', status: 'passed' },
      { label: 'Refresh', value: '240Hz', status: 'passed' },
      { label: 'Response', value: '0.03ms', status: 'passed' },
    ],
    tags: ['OLED', '240Hz', 'HDR10', 'Gaming'],
  },
  {
    id: 'thinkpad-x1',
    name: 'ThinkPad X1 Carbon',
    category: 'laptop',
    score: 87,
    price: '₹1,89,990',
    icon: '💻',
    specs: [
      { label: 'CPU', value: 'Core Ultra 7', status: 'passed' },
      { label: 'RAM', value: '32GB LPDDR5', status: 'passed' },
      { label: 'Display', value: '2.8K OLED', status: 'passed' },
      { label: 'Weight', value: '1.08 kg', status: 'passed' },
    ],
    tags: ['OLED', 'Ultralight', 'Business', 'Verified'],
  },
  {
    id: 'sony-wh1000xm5',
    name: 'WH-1000XM5',
    category: 'headphones',
    score: 89,
    price: '₹29,990',
    icon: '🎧',
    specs: [
      { label: 'Sound', value: 'Hi-Res Audio', status: 'passed' },
      { label: 'ANC', value: 'Industry Leading', status: 'passed' },
      { label: 'Battery', value: '30 Hours', status: 'passed' },
      { label: 'Codec', value: 'LDAC', status: 'passed' },
    ],
    tags: ['Hi-Res', 'ANC', 'Battery 30hr', 'Dolby Atmos'],
  },
  {
    id: 'ipad-pro-m4',
    name: 'iPad Pro 13" M4',
    category: 'tablet',
    score: 92,
    price: '₹1,12,900',
    icon: '📟',
    specs: [
      { label: 'Chip', value: 'Apple M4', status: 'passed' },
      { label: 'Display', value: 'XDR ProMotion', status: 'passed' },
      { label: 'Storage', value: '256GB', status: 'warning' },
      { label: 'Pencil', value: 'Apple Pencil Pro', status: 'passed' },
    ],
    tags: ['Apple M4', 'ProMotion', 'XDR', 'Creator'],
  },
];

// All available floating tags for the workspace
export const ALL_TAGS = [
  'RTX 4060', 'OLED', '120Hz', 'AI Pick', 'Best Value', 'Creator',
  'Gaming', 'Verified', 'Top Rated', 'IPS', 'Battery 9hr', '5G',
  'USB-C', 'HDR10', 'Dolby Atmos', 'ANC', '4K', 'Hi-Res',
  'Ultralight', 'S-Pen', '240Hz', 'Apple M4', 'RTX 4070',
];

// Analysis phases for status console
export const SCAN_PHASES = [
  'INITIALIZING SCAN VECTOR...',
  'EXTRACTING SPECIFICATIONS...',
  'RUNNING COMPATIBILITY CHECKS...',
  'CALCULATING MULTI-ATTRIBUTE SCORE...',
  'CROSS-REFERENCING CATALOG...',
  'LOCKING RECOMMENDATION SCORE...',
];
