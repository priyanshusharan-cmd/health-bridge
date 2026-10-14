"""Supported care-content languages. Interface coverage is explicit."""
GROUPS = [
    ('International', [('en','English')]),
    ('South Asia · North and West', [('hi','हिन्दी'),('mr','मराठी'),('gu','ગુજરાતી'),('pa','ਪੰਜਾਬੀ'),('ur','اردو'),('ne','नेपाली')]),
    ('South Asia · South', [('kn','ಕನ್ನಡ'),('ta','தமிழ்'),('te','తెలుగు'),('ml','മലയാളം'),('si','සිංහල')]),
    ('South Asia · East', [('bn','বাংলা'),('as','অসমীয়া'),('or','ଓଡ଼ିଆ')]),
    ('Middle East', [('ar','العربية'),('fa','فارسی')]),
    ('East and Southeast Asia', [('zh','中文'),('ja','日本語'),('ko','한국어'),('id','Bahasa Indonesia'),('vi','Tiếng Việt'),('th','ไทย')]),
    ('Europe and the Americas', [('es','Español'),('fr','Français'),('de','Deutsch'),('pt','Português'),('it','Italiano')]),
]
LANGUAGES = [dict(code=code, name=name, region=region, interface=code in ('en','hi','kn'), direction='rtl' if code in ('ar','fa','ur') else 'ltr') for region, entries in GROUPS for code,name in entries]
CODES = {item['code'] for item in LANGUAGES}
