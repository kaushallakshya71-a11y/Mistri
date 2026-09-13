/**
 * Mistri i18n - Hindi/English bilingual support
 * Usage: t('key') returns string in current language
 */

const TRANSLATIONS = {
    en: {
        // Dashboard
        welcome: "Welcome",
        overview: "Here's an overview of your repairs",
        newRepair: "➕ New Repair",
        totalRepairs: "Total Repairs",
        activeRepairs: "Active Repairs",
        completed: "Completed",
        unreadAlerts: "Unread Alerts",
        activeRepairsTitle: "Active Repairs",
        allRepairs: "All Repairs",
        noRepairsYet: "No repairs yet",
        submitFirstRepair: "Submit your first repair request",
        submitRepair: "➕ Submit Repair",

        // Repair detail
        repairProgress: "Repair Progress",
        problemDescription: "PROBLEM DESCRIPTION",
        deviceDetails: "DEVICE DETAILS",
        assignedTechnician: "ASSIGNED TECHNICIAN",
        estimatedCost: "ESTIMATED COST",
        submitted: "SUBMITTED",
        technicianNotes: "TECHNICIAN NOTES",
        notYetAssigned: "Not yet assigned",
        pending: "Pending",
        viewInvoices: "📄 View Invoices",
        qrCode: "📱 QR Code",

        // Submit repair
        submitRepairTitle: "➕ Submit Repair Request",
        submitRepairSub: "Fill in the details and get an AI cost estimate instantly",
        applianceType: "Appliance Type *",
        selectAppliance: "Select appliance...",
        brand: "Brand *",
        brandPlaceholder: "Crompton, Havells, Bajaj...",
        modelSize: "Model / Size *",
        modelPlaceholder: "Aura 48 inch, Diet 35i, GX-1...",
        problemDesc: "Problem Description *",
        problemPlaceholder: "Describe the issue in detail... (e.g., screen cracked, battery not charging, won't turn on)",
        uploadImage: "Upload Image (optional)",
        submitBtn: "🚀 Submit Repair Request",
        submitting: "Submitting...",
        estimating: "Estimating...",
        fillToEstimate: "Fill in device type and problem to get an estimate...",

        // AI Estimator
        aiEstimator: "🤖 AI Cost Estimator",
        estTime: "Est. Time",
        hours: "hours",
        mainPart: "Main Part",
        confidence: "Confidence",

        // Invoices
        myInvoices: "📄 My Invoices",
        downloadInvoices: "Download PDF invoices for your repairs",
        noInvoicesYet: "No invoices yet",
        billNum: "Bill #",
        repairId: "Repair ID",
        device: "Device",
        amount: "Amount",
        status: "Status",
        date: "Date",
        action: "Action",

        // Feedback
        leaveReview: "⭐ Leave a Review",
        feedbackDesc: "Your repair is complete! Tell us how we did.",
        selectRating: "Select rating:",
        comment: "Comment (optional)",
        commentPlaceholder: "How was your experience?",
        submitFeedback: "Submit Feedback",
        feedbackThanks: "🙏 Thank you for your feedback!",
        alreadyFeedback: "✅ You've already reviewed this repair.",
        feedbackError: "Could not submit feedback. Please try again.",

        // Navigation
        back: "← Back",
        language: "हिं",
    },
    hi: {
        // Dashboard
        welcome: "स्वागत है",
        overview: "आपकी मरम्मत की संक्षिप्त जानकारी",
        newRepair: "➕ नई मरम्मत",
        totalRepairs: "कुल मरम्मत",
        activeRepairs: "चल रही मरम्मत",
        completed: "पूर्ण",
        unreadAlerts: "अपठित सूचनाएं",
        activeRepairsTitle: "चल रही मरम्मत",
        allRepairs: "सभी मरम्मत",
        noRepairsYet: "अभी कोई मरम्मत नहीं",
        submitFirstRepair: "अपनी पहली मरम्मत अनुरोध सबमिट करें",
        submitRepair: "➕ मरम्मत सबमिट करें",

        // Repair detail
        repairProgress: "मरम्मत की प्रगति",
        problemDescription: "समस्या विवरण",
        deviceDetails: "डिवाइस विवरण",
        assignedTechnician: "नियुक्त तकनीशियन",
        estimatedCost: "अनुमानित लागत",
        submitted: "सबमिट किया",
        technicianNotes: "तकनीशियन नोट्स",
        notYetAssigned: "अभी नियुक्त नहीं",
        pending: "लंबित",
        viewInvoices: "📄 चालान देखें",
        qrCode: "📱 QR कोड",

        // Submit repair
        submitRepairTitle: "➕ मरम्मत अनुरोध सबमिट करें",
        submitRepairSub: "विवरण भरें और तुरंत AI लागत अनुमान पाएं",
        applianceType: "उपकरण का प्रकार *",
        selectAppliance: "उपकरण चुनें...",
        brand: "ब्रांड *",
        brandPlaceholder: "क्रॉम्पटन, हैवेल्स, बजाज...",
        modelSize: "मॉडल / आकार *",
        modelPlaceholder: "Aura 48 inch, Diet 35i, GX-1...",
        problemDesc: "समस्या विवरण *",
        problemPlaceholder: "समस्या विस्तार से बताएं... (जैसे: पंखा नहीं चल रहा, पानी नहीं आ रहा)",
        uploadImage: "छवि अपलोड करें (वैकल्पिक)",
        submitBtn: "🚀 मरम्मत अनुरोध सबमिट करें",
        submitting: "सबमिट हो रहा है...",
        estimating: "अनुमान लगाया जा रहा है...",
        fillToEstimate: "अनुमान के लिए उपकरण प्रकार और समस्या भरें...",

        // AI Estimator
        aiEstimator: "🤖 AI लागत अनुमानक",
        estTime: "अनुमानित समय",
        hours: "घंटे",
        mainPart: "मुख्य पुर्जा",
        confidence: "विश्वास",

        // Invoices
        myInvoices: "📄 मेरे चालान",
        downloadInvoices: "अपनी मरम्मत के PDF चालान डाउनलोड करें",
        noInvoicesYet: "अभी कोई चालान नहीं",
        billNum: "बिल #",
        repairId: "मरम्मत ID",
        device: "उपकरण",
        amount: "राशि",
        status: "स्थिति",
        date: "तारीख",
        action: "कार्रवाई",

        // Feedback
        leaveReview: "⭐ समीक्षा दें",
        feedbackDesc: "आपकी मरम्मत पूरी हो गई! बताइए हमने कैसा काम किया।",
        selectRating: "रेटिंग चुनें:",
        comment: "टिप्पणी (वैकल्पिक)",
        commentPlaceholder: "आपका अनुभव कैसा रहा?",
        submitFeedback: "प्रतिक्रिया सबमिट करें",
        feedbackThanks: "🙏 आपकी प्रतिक्रिया के लिए धन्यवाद!",
        alreadyFeedback: "✅ आप इस मरम्मत की समीक्षा दे चुके हैं।",
        feedbackError: "प्रतिक्रिया सबमिट नहीं हो सकी। कृपया पुनः प्रयास करें।",

        // Navigation
        back: "← वापस",
        language: "EN",
    }
};

function getLang() {
    return localStorage.getItem('mistri_lang') || 'en';
}

function setLang(lang) {
    localStorage.setItem('mistri_lang', lang);
}

function t(key) {
    const lang = getLang();
    return (TRANSLATIONS[lang] && TRANSLATIONS[lang][key]) || TRANSLATIONS['en'][key] || key;
}

function toggleLanguage() {
    const current = getLang();
    const next = current === 'en' ? 'hi' : 'en';
    setLang(next);
    // Re-render current view
    if (typeof router !== 'undefined' && router._currentRoute) {
        router.navigate(router._currentRoute);
    } else {
        window.location.reload();
    }
}

function langToggleBtn() {
    return `<button class="btn btn-outline btn-sm lang-toggle-btn" onclick="toggleLanguage()" title="Switch Language" style="min-width:52px;font-weight:700;font-size:0.85rem;">🌐 ${t('language')}</button>`;
}
