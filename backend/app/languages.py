"""Supported care-content and interface languages."""
GROUPS = [
    ('International', [('en', 'English')]),
    ('Scheduled Languages of India', [
        ('as', 'অসমীয়া (Assamese)'),
        ('bn', 'বাংলা (Bengali)'),
        ('brx', 'बड़ो (Bodo)'),
        ('doi', 'डोगरी (Dogri)'),
        ('gu', 'ગુજરાતી (Gujarati)'),
        ('hi', 'हिन्दी (Hindi)'),
        ('kn', 'ಕನ್ನಡ (Kannada)'),
        ('ks', 'کٲشُر / कॉशुर (Kashmiri)'),
        ('kok', 'कोंकणी (Konkani)'),
        ('mai', 'मैथिली (Maithili)'),
        ('ml', 'മലയാളം (Malayalam)'),
        ('mni', 'মৈতৈলোন্ (Manipuri)'),
        ('mr', 'मराठी (Marathi)'),
        ('ne', 'नेपाली (Nepali)'),
        ('or', 'ଓଡ଼ିଆ (Odia)'),
        ('pa', 'ਪੰਜਾਬੀ (Punjabi)'),
        ('sa', 'संस्कृतम् (Sanskrit)'),
        ('sat', 'ᱥᱟᱱᱛᱟᱲᱤ (Santali)'),
        ('sd', 'سنڌي / सिन्धी (Sindhi)'),
        ('ta', 'தமிழ் (Tamil)'),
        ('te', 'తెలుగు (Telugu)'),
        ('ur', 'اردو (Urdu)'),
    ]),
    ('Other World Languages', [
        ('ar', 'العربية (Arabic)'),
        ('fa', 'فارسی (Persian)'),
        ('zh', '中文 (Chinese)'),
        ('ja', '日本語 (Japanese)'),
        ('ko', '한국어 (Korean)'),
        ('es', 'Español (Spanish)'),
        ('fr', 'Français (French)'),
        ('de', 'Deutsch (German)'),
    ]),
]
LANGUAGES = [
    dict(
        code=code,
        name=name,
        region=region,
        interface=True,
        direction='rtl' if code in ('ar', 'fa', 'ur', 'ks', 'sd') else 'ltr',
    )
    for region, entries in GROUPS
    for code, name in entries
]
CODES = {item['code'] for item in LANGUAGES}
