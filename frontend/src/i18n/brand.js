// Product language takes precedence over legacy terminology overlays.
const brand = {
  en: {"nav.dashboard":"Home", "nav.recommendations":"Find a place", "nav.requests":"Applications", "nav.profile":"Profile", "recommend.heading":"PICKED FOR YOUR BUSINESS", "recommend.eligible":"{count} eligible places · availability checked with NMC"},
  mr: {"nav.dashboard":"मुख्यपृष्ठ", "nav.recommendations":"जागा शोधा", "nav.requests":"अर्ज", "nav.profile":"प्रोफाइल"},
  hi: {"nav.dashboard":"होम", "nav.recommendations":"जगह खोजें", "nav.requests":"आवेदन", "nav.profile":"प्रोफ़ाइल"},
};

Object.assign(brand.en, {
  "account.changePhoto":"Change photo", "account.uploadPhoto":"Add photo", "account.photoUploading":"Updating…",
  "account.photoSaved":"Profile photo updated.", "account.photoPreview":"Profile photo of {name}", "account.downloadIdCard":"Download identity summary", "account.preparingIdCard":"Preparing summary…",
  "card.title":"Vendor identity summary", "card.applicationReference":"Application vendor ID", "card.vendorReference":"Historical vendor ID", "card.currentZone":"Current vending zone", "card.noZone":"No active allocation", "card.notice":"Profile summary. Not a vending permit."
});
Object.assign(brand.mr, {
  "account.changePhoto":"फोटो बदला", "account.uploadPhoto":"फोटो जोडा", "account.photoUploading":"बदलत आहे…",
  "account.photoSaved":"प्रोफाइल फोटो अद्ययावत झाला.", "account.photoPreview":"{name} यांचा प्रोफाइल फोटो", "account.downloadIdCard":"ओळख सारांश डाउनलोड करा", "account.preparingIdCard":"सारांश तयार होत आहे…",
  "card.title":"विक्रेता ओळख सारांश", "card.applicationReference":"अर्जदार विक्रेता आयडी", "card.vendorReference":"ऐतिहासिक विक्रेता आयडी", "card.currentZone":"सध्याचा विक्री झोन", "card.noZone":"सध्या जागा वाटप नाही", "card.notice":"प्रोफाइल सारांश. हा विक्री परवाना नाही."
});
Object.assign(brand.hi, {
  "account.changePhoto":"फ़ोटो बदलें", "account.uploadPhoto":"फ़ोटो जोड़ें", "account.photoUploading":"अपडेट हो रहा है…",
  "account.photoSaved":"प्रोफ़ाइल फ़ोटो अपडेट हो गई.", "account.photoPreview":"{name} की प्रोफ़ाइल फ़ोटो", "account.downloadIdCard":"पहचान सारांश डाउनलोड करें", "account.preparingIdCard":"सारांश तैयार हो रहा है…",
  "card.title":"विक्रेता पहचान सारांश", "card.applicationReference":"आवेदक विक्रेता आईडी", "card.vendorReference":"ऐतिहासिक विक्रेता आईडी", "card.currentZone":"वर्तमान विक्रय ज़ोन", "card.noZone":"अभी कोई आवंटन नहीं", "card.notice":"प्रोफ़ाइल सारांश. यह विक्रय परमिट नहीं है."
});
Object.assign(brand.en, {
  "pwa.installTitle":"Install VendorMap", "pwa.installText":"Keep VendorMap close at hand.", "pwa.install":"Install", "pwa.how":"How to install", "pwa.iosGuide":"Tap Share in your browser, then Add to Home Screen and Add. If the option is missing, open VendorMap in Safari.",
  "pwa.updateTitle":"App update", "pwa.updateText":"A new version is ready. Reload when you’re ready.", "pwa.reload":"Reload",
  "pwa.offlineTitle":"Connection needed", "pwa.offlineText":"Reconnect to view current places, applications and allocation information. Private information is not available offline.", "pwa.retry":"Try again"
});
Object.assign(brand.mr, {
  "pwa.installTitle":"VendorMap इन्स्टॉल करा", "pwa.installText":"VendorMap तुमच्या होम स्क्रीनवर ठेवा.", "pwa.install":"इन्स्टॉल करा", "pwa.how":"कसे इन्स्टॉल करावे", "pwa.iosGuide":"ब्राउझरमध्ये शेअर निवडा, नंतर होम स्क्रीनवर जोडा आणि जोडा निवडा. पर्याय दिसत नसल्यास VendorMap Safari मध्ये उघडा.",
  "pwa.updateTitle":"ॲप अपडेट", "pwa.updateText":"नवीन आवृत्ती तयार आहे. सोयीनुसार पुन्हा लोड करा.", "pwa.reload":"पुन्हा लोड करा",
  "pwa.offlineTitle":"इंटरनेट जोडणी आवश्यक", "pwa.offlineText":"सध्याच्या जागा, अर्ज आणि वाटपाची माहिती पाहण्यासाठी पुन्हा इंटरनेटशी जोडा. खाजगी माहिती ऑफलाइन उपलब्ध नाही.", "pwa.retry":"पुन्हा प्रयत्न करा"
});
Object.assign(brand.hi, {
  "pwa.installTitle":"VendorMap इंस्टॉल करें", "pwa.installText":"VendorMap अपनी होम स्क्रीन पर रखें.", "pwa.install":"इंस्टॉल करें", "pwa.how":"कैसे इंस्टॉल करें", "pwa.iosGuide":"ब्राउज़र में शेयर चुनें, फिर होम स्क्रीन पर जोड़ें और जोड़ें चुनें. विकल्प नहीं दिखने पर VendorMap को Safari में खोलें.",
  "pwa.updateTitle":"ऐप अपडेट", "pwa.updateText":"नया संस्करण तैयार है. अपनी सुविधा से फिर लोड करें.", "pwa.reload":"फिर लोड करें",
  "pwa.offlineTitle":"इंटरनेट कनेक्शन ज़रूरी है", "pwa.offlineText":"वर्तमान जगहों, आवेदनों और आवंटन की जानकारी देखने के लिए फिर से कनेक्ट करें. निजी जानकारी ऑफलाइन उपलब्ध नहीं है.", "pwa.retry":"फिर कोशिश करें"
});
export default brand;
