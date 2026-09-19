/**
 * Mistri App Bootstrap
 * Registers all routes and initializes the SPA
 */

// Register all routes
router.register('/', renderLandingPage);
router.register('/login', renderLogin);
router.register('/register', renderRegister);
router.register('/logout', () => logout());

// Public repair tracker
router.register('/track/*', renderRepairTracker);

// Customer routes
router.register('/customer', renderCustomerDashboard);
router.register('/customer/submit', renderSubmitRepair);
router.register('/customer/invoices', renderCustomerInvoices);
router.register('/customer/offers', renderCustomerOffers);
router.register('/customer/support', renderCustomerSupport);

// Admin routes
router.register('/admin', renderAdminDashboard);
router.register('/admin/repairs', renderAdminRepairs);
router.register('/admin/customers', renderAdminCustomers);
router.register('/admin/inventory', renderAdminInventory);
router.register('/admin/reports', renderAdminReports);
router.register('/admin/staff', renderAdminStaff);
router.register('/admin/bills', renderAdminBills);
router.register('/admin/offers', renderAdminOffers);
router.register('/admin/support', renderAdminSupportTickets);
router.register('/admin/payments', renderAdminPaymentsReport);
router.register('/admin/feedback', renderAdminFeedback);
router.register('/admin/warranties', renderAdminWarranties);
router.register('/admin/audit-logs', renderAdminAuditLogs);

// Staff routes
router.register('/staff', renderStaffDashboard);
router.register('/staff/leaves', renderStaffLeavesAndSalary);
router.register('/staff/inventory', renderStaffInventory);

// Shop routes
router.register('/shop', renderShop);
router.register('/shop/cart', renderCart);
router.register('/shop/orders', renderMyOrders);
router.register('/shop/admin', renderAdminShop);

// Theme toggle
const themeBtn = document.getElementById('theme-btn');
const savedTheme = localStorage.getItem('mistri_theme') || 'dark';
document.documentElement.setAttribute('data-theme', savedTheme);
themeBtn.textContent = savedTheme === 'dark' ? '☀️' : '🌙';

themeBtn.addEventListener('click', () => {
    const current = document.documentElement.getAttribute('data-theme');
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('mistri_theme', next);
    themeBtn.textContent = next === 'dark' ? '☀️' : '🌙';
    window.dispatchEvent(new CustomEvent('themeChanged', { detail: { theme: next } }));
});

// Notification button
document.getElementById('notif-btn').addEventListener('click', (e) => {
    e.stopPropagation();
    openNotifPanel();
});

// Remove loading screen after app is initialized
function hideLoading() {
    const loader = document.getElementById('loading-screen');
    if (loader) {
        loader.style.opacity = '0';
        loader.style.transition = 'opacity 0.3s ease';
        setTimeout(() => {
            if (loader && loader.parentNode) loader.remove();
        }, 300);
    }
}

// Start the app with error resilience
document.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => {
        try {
            hideLoading();
            router.start();
        } catch (e) {
            console.error('Router start error:', e);
            hideLoading();
        }
    }, 600);
});

// Failsafe: if DOMContentLoaded already fired or delayed
setTimeout(() => {
    try {
        hideLoading();
        if (!router.currentRoute) router.start();
    } catch (e) {
        hideLoading();
    }
}, 2000);
