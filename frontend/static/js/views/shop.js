/**
 * Mistri - Shop View (Buy & Sell)
 */

let shopProducts = [];
let currentCategory = 'All';
let cart = JSON.parse(localStorage.getItem('mistri_cart')) || [];

// Save cart to local storage
function saveCart() {
    localStorage.setItem('mistri_cart', JSON.stringify(cart));
    updateCartBadge();
}

// Add an item to cart
function addToCart(productId, name, price, brand, sizeVariant) {
    const existing = cart.find(i => i.product_id === productId);
    if (existing) {
        existing.quantity += 1;
    } else {
        cart.push({
            product_id: productId,
            name: name,
            price: price,
            brand: brand,
            size_variant: sizeVariant,
            quantity: 1
        });
    }
    saveCart();
    showToast(`${name} added to cart`, 'success');
}

// Update cart badge icon in navbar
function updateCartBadge() {
    const cartBtn = document.getElementById('cart-nav-btn');
    if (!cartBtn) return;
    const totalItems = cart.reduce((sum, item) => sum + item.quantity, 0);
    const badge = cartBtn.querySelector('.notif-badge');
    if (badge) {
        badge.textContent = totalItems;
        badge.style.display = totalItems > 0 ? 'flex' : 'none';
    }
}

// --- Public Shop Page --- //

async function renderShop() {
    showLoading();
    try {
        shopProducts = await api.get('/shop/products');

        const categories = ['All', 'Plug', 'Wire', 'Mixer Pot', 'Switch', 'Other'];

        setContent(`
            <div class="page-header">
                <div>
                    <h2>🛒 Electrical parts & components</h2>
                    <p class="text-muted">Buy spare parts directly from Mistri Shop</p>
                </div>
                <div class="header-actions">
                    <button class="btn btn-primary" onclick="router.navigate('/shop/cart')">
                        Shopping Cart 🛍️
                        <span class="badge badge-success" style="margin-left:8px; display:${cart.length > 0 ? 'inline-block' : 'none'}">${cart.reduce((sum, i) => sum + i.quantity, 0)}</span>
                    </button>
                    ${api.getUser()?.role === 'admin' ? `<button class="btn btn-outline" onclick="router.navigate('/shop/admin')">🧑‍💼 Manage Products</button>` : ''}
                </div>
            </div>

            <div class="shop-container" style="display: flex; gap: 2rem; margin-top: 1.5rem;">
                <!-- Sidebar Filters -->
                <div class="shop-sidebar" style="width: 250px; flex-shrink: 0;">
                    <div class="card">
                        <h3>Categories</h3>
                        <div class="filter-list" style="display: flex; flex-direction: column; gap: 0.5rem; margin-top: 1rem;">
                            ${categories.map(cat => `
                                <button class="btn ${currentCategory === cat ? 'btn-primary' : 'btn-outline'}" 
                                        style="text-align: left; justify-content: flex-start;"
                                        onclick="filterShopProducts('${cat}')">
                                    ${cat}
                                </button>
                            `).join('')}
                        </div>
                    </div>
                </div>

                <!-- Product Grid -->
                <div class="shop-main" style="flex-grow: 1;">
                    <div class="product-grid" id="productGrid" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 1.5rem;">
                        <!-- Products injected here -->
                    </div>
                </div>
            </div>
        `);

        filterShopProducts(currentCategory);
    } catch (e) {
        setContent(`<div class="api-error">Error loading shop: ${e.message}</div>`);
    }
}

function filterShopProducts(category) {
    currentCategory = category;

    // Update active state of filter buttons
    document.querySelectorAll('.filter-list .btn').forEach(btn => {
        if (btn.textContent.trim() === category) {
            btn.classList.add('btn-primary');
            btn.classList.remove('btn-outline');
        } else {
            btn.classList.remove('btn-primary');
            btn.classList.add('btn-outline');
        }
    });

    const filtered = category === 'All' ? shopProducts : shopProducts.filter(p => p.category === category);
    const grid = document.getElementById('productGrid');

    if (filtered.length === 0) {
        grid.innerHTML = `
            <div class="empty-state" style="grid-column: 1 / -1; padding: 3rem;">
                <div class="empty-state-icon">🚫</div>
                <div class="empty-state-title">No products found</div>
                <p>We couldn't find any products in the ${category} category.</p>
            </div>
        `;
        return;
    }

    grid.innerHTML = filtered.map(p => {
        const outOfStock = p.stock_qty <= 0;
        const brandBadge = p.brand ? `<span class="badge badge-pending" style="font-size: 0.7rem; margin-bottom: 0.5rem; display: inline-block;">${p.brand}</span>` : '';
        const sizeInfo = p.size_variant ? `<div class="text-sm" style="color:var(--text-light); margin-bottom: 0.5rem;">Size/Spec: ${p.size_variant}</div>` : '';

        return `
            <div class="card product-card ${outOfStock ? 'out-of-stock' : ''}" style="display: flex; flex-direction: column; height: 100%; transition: transform 0.2s;">
                <div style="aspect-ratio: 4/3; background: var(--bg-color); border-radius: 8px; margin-bottom: 1rem; display: flex; align-items: center; justify-content: center; overflow: hidden;">
                    ${p.image_url ?
                `<img src="${p.image_url}" alt="${p.name}" style="width: 100%; height: 100%; object-fit: cover;">` :
                `<span style="font-size: 3rem; color: var(--border-color);">📦</span>`
            }
                </div>
                <div style="flex-grow: 1;">
                    ${brandBadge}
                    <h4 style="margin: 0 0 0.5rem 0; font-size: 1.1rem; line-height: 1.4;">${p.name}</h4>
                    ${sizeInfo}
                    <div style="font-size: 1.25rem; font-weight: 700; color: var(--primary-color); margin-bottom: 0.5rem;">
                        ${formatCurrency(p.price)}
                    </div>
                    ${p.description ? `<p class="text-muted text-sm" style="display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;">${p.description}</p>` : ''}
                </div>
                
                <div style="margin-top: 1rem; padding-top: 1rem; border-top: 1px solid var(--border-color); display: flex; justify-content: space-between; align-items: center;">
                    <span class="text-sm ${outOfStock ? 'text-danger' : 'text-success'}">
                        ${outOfStock ? '❌ Out of stock' : `✅ In stock (${p.stock_qty})`}
                    </span>
                    <button class="btn btn-primary btn-sm" 
                            style="padding: 0.5rem 1rem;" 
                            ${outOfStock ? 'disabled' : ''}
                            onclick="addToCart(${p.id}, '${p.name.replace(/'/g, "\\'")}', ${p.price}, '${p.brand || ''}', '${p.size_variant || ''}')">
                        Add to Cart 🛒
                    </button>
                </div>
            </div>
        `;
    }).join('');
}

// --- Cart & Checkout Page --- //

function renderCart() {
    const totalAmount = cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);

    let cartContent = '';

    if (cart.length === 0) {
        cartContent = `
            <div class="empty-state" style="padding: 4rem;">
                <div class="empty-state-icon">🛒</div>
                <div class="empty-state-title">Your cart is empty</div>
                <p>Browse the shop to add some electrical components.</p>
                <button class="btn btn-primary" onclick="router.navigate('/shop')" style="margin-top: 1.5rem;">Go to Shop</button>
            </div>
        `;
    } else {
        cartContent = `
            <div style="display: grid; grid-template-columns: 2fr 1fr; gap: 2rem; margin-top: 1.5rem;">
                <div class="cart-items">
                    <div class="card">
                        <table class="data-table">
                            <thead>
                                <tr>
                                    <th>Product</th>
                                    <th>Price</th>
                                    <th>Quantity</th>
                                    <th>Total</th>
                                    <th>Action</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${cart.map((item, i) => `
                                    <tr>
                                        <td>
                                            <div style="font-weight: 500">${item.name}</div>
                                            <div class="text-muted text-sm">${item.brand ? item.brand + ' - ' : ''}${item.size_variant || ''}</div>
                                        </td>
                                        <td>${formatCurrency(item.price)}</td>
                                        <td>
                                            <div style="display: inline-flex; align-items: center; border: 1px solid var(--border-color); border-radius: 4px; overflow: hidden;">
                                                <button style="padding: 4px 10px; background: var(--bg-color); border: none; cursor: pointer;" onclick="updateCartItemQty(${i}, -1)">-</button>
                                                <span style="padding: 4px 12px; font-weight:500;">${item.quantity}</span>
                                                <button style="padding: 4px 10px; background: var(--bg-color); border: none; cursor: pointer; border-left: 1px solid var(--border-color);" onclick="updateCartItemQty(${i}, 1)">+</button>
                                            </div>
                                        </td>
                                        <td style="font-weight: 600;">${formatCurrency(item.price * item.quantity)}</td>
                                        <td>
                                            <button class="icon-btn text-danger" onclick="removeFromCart(${i})" title="Remove item">🗑️</button>
                                        </td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                </div>
                
                <div class="checkout-panel">
                    <div class="card" style="position: sticky; top: 80px;">
                        <h3>Order Summary</h3>
                        <div style="display: flex; justify-content: space-between; margin: 1rem 0; padding-bottom: 1rem; border-bottom: 1px solid var(--border-color);">
                            <span>Items (${cart.reduce((s, i) => s + i.quantity, 0)}):</span>
                            <span>${formatCurrency(totalAmount)}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; margin-bottom: 1.5rem; font-size: 1.25rem; font-weight: 700;">
                            <span>Total Array:</span>
                            <span class="text-primary">${formatCurrency(totalAmount)}</span>
                        </div>
                        
                        <form id="checkoutForm" onsubmit="event.preventDefault(); placeOrder();">
                            <div class="form-group">
                                <label>Delivery Address / Notes</label>
                                <textarea id="checkoutAddress" class="form-control" rows="3" placeholder="Enter delivery address or pickup instructions" required></textarea>
                            </div>
                            <div class="form-group">
                                <label>Payment Method</label>
                                <select id="checkoutPayment" class="form-control">
                                    <option value="Cash on Delivery">Cash on Delivery</option>
                                    <option value="UPI / Online">UPI / Online</option>
                                </select>
                            </div>
                            <button type="submit" class="btn btn-primary" style="width: 100%; justify-content: center; font-size: 1.1rem; padding: 0.8rem;">
                                Place Order 🚀
                            </button>
                        </form>
                    </div>
                </div>
            </div>
        `;
    }

    setContent(`
        <div class="page-header">
            <div>
                <h2>Your Shopping Cart</h2>
                <div class="breadcrumbs">
                    <a href="#/shop" style="color:var(--text-light); text-decoration:none;">Shop</a> &rsaquo; Cart
                </div>
            </div>
        </div>
        ${cartContent}
    `);
}

function updateCartItemQty(index, change) {
    const item = cart[index];
    item.quantity += change;
    if (item.quantity <= 0) {
        removeFromCart(index);
    } else {
        saveCart();
        renderCart();
    }
}

function removeFromCart(index) {
    cart.splice(index, 1);
    saveCart();
    renderCart();
}

async function placeOrder() {
    const address = document.getElementById('checkoutAddress').value;
    const payment = document.getElementById('checkoutPayment').value;
    const totalAmount = cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);

    const payload = {
        items: cart,
        total_amount: totalAmount,
        delivery_address: address,
        payment_method: payment,
        notes: "Placed from web interface"
    };

    try {
        const res = await api.post('/shop/orders', payload);
        showToast(res.message, 'success');

        // Clear cart
        cart = [];
        saveCart();

        // redirect to orders history
        router.navigate('/shop/orders');
    } catch (e) {
        showToast(e.message, 'error');
    }
}

// --- Customer Order History Page --- //

async function renderMyOrders() {
    showLoading();
    try {
        const orders = await api.get('/shop/orders/mine');

        const tableHtml = orders.length === 0
            ? `<div class="empty-state"><div class="empty-state-icon">📦</div><div class="empty-state-title">No orders yet</div></div>`
            : `<table class="data-table">
                  <thead>
                      <tr>
                          <th>Order #</th>
                          <th>Date</th>
                          <th>Items</th>
                          <th>Total</th>
                          <th>Status</th>
                          <th>Payment</th>
                      </tr>
                  </thead>
                  <tbody>
                      ${orders.map(o => {
                const items = JSON.parse(o.items);
                const itemsSummary = items.map(i => `${i.quantity}x ${i.name}`).join(', ');

                let statusClass = 'pending';
                if (o.status === 'Confirmed') statusClass = 'success';
                else if (o.status === 'Cancelled') statusClass = 'danger';
                else if (o.status === 'Delivered') statusClass = 'success';
                else if (o.status === 'Shipped') statusClass = 'primary';

                return `
                          <tr>
                              <td style="font-weight:600; font-family:monospace;">${o.order_number}</td>
                              <td>${formatDate(o.created_at)}</td>
                              <td><div style="max-width: 250px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${itemsSummary}">${itemsSummary}</div></td>
                              <td style="font-weight:600;">${formatCurrency(o.total_amount)}</td>
                              <td><span class="badge badge-${statusClass}">${o.status}</span></td>
                              <td>${o.payment_method}</td>
                          </tr>
                      `}).join('')}
                  </tbody>
               </table>`;

        setContent(`
            <div class="page-header">
                <div>
                    <h2>My Shop Orders</h2>
                    <p class="text-muted">Track your recent purchases</p>
                </div>
                <div class="header-actions">
                    <button class="btn btn-outline" onclick="router.navigate('/shop')">Browse Shop 🛒</button>
                </div>
            </div>
            <div class="card">
                ${tableHtml}
            </div>
        `);
    } catch (e) {
        setContent(`<div class="api-error">Error loading orders: ${e.message}</div>`);
    }
}

// --- Admin Shop Management Page --- //

async function renderAdminShop() {
    showLoading();
    try {
        const [products, orders] = await Promise.all([
            api.get('/shop/products'), // admins get all, including inactive
            api.get('/shop/orders')
        ]);

        setContent(`
            <div class="page-header">
                <div>
                    <h2>Shop Management</h2>
                    <p class="text-muted">Manage products and customer orders</p>
                </div>
                <div class="header-actions">
                    <button class="btn btn-primary" onclick="showAddProductModal()">+ Add Product</button>
                </div>
            </div>
            
            <div class="tabs" style="margin-bottom: 1.5rem; display: flex; gap: 1rem; border-bottom: 1px solid var(--border-color); padding-bottom: 0.5rem;">
                <button class="btn btn-primary" id="tab-products" onclick="switchAdminShopTab('products')" style="border-radius: 4px;">Products</button>
                <button class="btn btn-outline" id="tab-orders" onclick="switchAdminShopTab('orders')" style="border-radius: 4px;">Orders <span class="badge badge-pending" style="margin-left:8px">${orders.filter(o => o.status === 'Pending').length}</span></button>
            </div>
            
            <div id="admin-products-view">
                <div class="card">
                    <table class="data-table">
                        <thead>
                            <tr>
                                <th>Name</th>
                                <th>Category</th>
                                <th>Brand / Size</th>
                                <th>Price</th>
                                <th>Stock</th>
                                <th>Status</th>
                                <th>Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${products.map(p => `
                                <tr>
                                    <td>
                                        <div style="font-weight: 500">${p.name}</div>
                                    </td>
                                    <td>${p.category}</td>
                                    <td>${p.brand || '-'} / ${p.size_variant || '-'}</td>
                                    <td>${formatCurrency(p.price)}</td>
                                    <td class="${p.stock_qty <= (p.reorder_level || 5) ? 'text-danger' : ''}">${p.stock_qty} ${p.unit || ''}</td>
                                    <td><span class="badge badge-${p.is_active ? 'success' : 'pending'}">${p.is_active ? 'Active' : 'Draft'}</span></td>
                                    <td>
                                        <button class="icon-btn text-primary" onclick='showEditProductModal(${JSON.stringify(p).replace(/'/g, "&#39;")})' title="Edit">✏️</button>
                                        <button class="icon-btn text-danger" onclick="deleteShopProduct(${p.id})" title="Delete">🗑️</button>
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
            
            <div id="admin-orders-view" style="display: none;">
                <div class="card">
                    <table class="data-table">
                        <thead>
                            <tr>
                                <th>Order #</th>
                                <th>Customer</th>
                                <th>Date</th>
                                <th>Total</th>
                                <th>Status</th>
                                <th>Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${orders.map(o => `
                                <tr>
                                    <td style="font-family: monospace; font-weight: 500;">${o.order_number}</td>
                                    <td>
                                        <div>${o.customer_name}</div>
                                        <div class="text-sm text-muted">${o.customer_phone}</div>
                                    </td>
                                    <td>${formatDate(o.created_at)}</td>
                                    <td>${formatCurrency(o.total_amount)}</td>
                                    <td><span class="badge badge-${o.status.toLowerCase()}">${o.status}</span></td>
                                    <td>
                                        <select class="form-control" style="width: auto; padding: 0.25rem; font-size: 0.9rem;" 
                                                onchange="updateShopOrderStatus(${o.id}, this.value)"
                                                ${['Delivered', 'Cancelled'].includes(o.status) ? 'disabled' : ''}>
                                            <option value="Pending" ${o.status === 'Pending' ? 'selected' : ''}>Pending</option>
                                            <option value="Confirmed" ${o.status === 'Confirmed' ? 'selected' : ''}>Confirmed</option>
                                            <option value="Shipped" ${o.status === 'Shipped' ? 'selected' : ''}>Shipped</option>
                                            <option value="Delivered" ${o.status === 'Delivered' ? 'selected' : ''}>Delivered</option>
                                            <option value="Cancelled" ${o.status === 'Cancelled' ? 'selected' : ''}>Cancelled</option>
                                        </select>
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        `);
    } catch (e) {
        setContent(`<div class="api-error">Error loading admin shop: ${e.message}</div>`);
    }
}

function switchAdminShopTab(tab) {
    if (tab === 'products') {
        document.getElementById('admin-products-view').style.display = 'block';
        document.getElementById('admin-orders-view').style.display = 'none';
        document.getElementById('tab-products').className = 'btn btn-primary';
        document.getElementById('tab-orders').className = 'btn btn-outline';
    } else {
        document.getElementById('admin-products-view').style.display = 'none';
        document.getElementById('admin-orders-view').style.display = 'block';
        document.getElementById('tab-products').className = 'btn btn-outline';
        document.getElementById('tab-orders').className = 'btn btn-primary';
    }
}

async function updateShopOrderStatus(orderId, newStatus) {
    try {
        await api.patch(`/shop/orders/${orderId}/status`, { status: newStatus });
        showToast(`Order status updated to ${newStatus}`, 'success');
        renderAdminShop();
    } catch (e) {
        showToast(`Failed to update status: ${e.message}`, 'error');
    }
}

function showAddProductModal() {
    showModal(`
        <h2>Add Shop Product</h2>
        <form onsubmit="event.preventDefault(); saveShopProduct();">
            <div class="form-group">
                <label>Product Name*</label>
                <input type="text" id="prod-name" class="form-control" required>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
                <div class="form-group">
                    <label>Category*</label>
                    <select id="prod-cat" class="form-control" required>
                        <option value="Plug">Plug</option>
                        <option value="Wire">Wire</option>
                        <option value="Mixer Pot">Mixer Pot</option>
                        <option value="Switch">Switch</option>
                        <option value="Other">Other</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Price (₹)*</label>
                    <input type="number" id="prod-price" class="form-control" step="0.01" required>
                </div>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
                <div class="form-group">
                    <label>Brand</label>
                    <input type="text" id="prod-brand" class="form-control">
                </div>
                <div class="form-group">
                    <label>Size / Variant</label>
                    <input type="text" id="prod-size" class="form-control" placeholder="e.g. 1.5mm, 3-Pin">
                </div>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
                <div class="form-group">
                    <label>Initial Stock*</label>
                    <input type="number" id="prod-stock" class="form-control" required min="0">
                </div>
                <div class="form-group">
                    <label>Status</label>
                    <select id="prod-active" class="form-control">
                        <option value="true">Active (Visible to users)</option>
                        <option value="false">Draft (Hidden)</option>
                    </select>
                </div>
            </div>
            <div class="form-actions" style="margin-top: 1.5rem; display: flex; justify-content: flex-end; gap: 1rem;">
                <button type="button" class="btn btn-outline" onclick="document.querySelector('.modal-overlay').remove()">Cancel</button>
                <button type="submit" class="btn btn-primary">Save Product</button>
            </div>
        </form>
    `);
}

function showEditProductModal(p) {
    showModal(`
        <h2>Edit Shop Product</h2>
        <form onsubmit="event.preventDefault(); saveShopProduct(${p.id});">
            <div class="form-group">
                <label>Product Name*</label>
                <input type="text" id="prod-name" class="form-control" value="${p.name}" required>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
                <div class="form-group">
                    <label>Category*</label>
                    <select id="prod-cat" class="form-control" required>
                        <option value="Plug" ${p.category === 'Plug' ? 'selected' : ''}>Plug</option>
                        <option value="Wire" ${p.category === 'Wire' ? 'selected' : ''}>Wire</option>
                        <option value="Mixer Pot" ${p.category === 'Mixer Pot' ? 'selected' : ''}>Mixer Pot</option>
                        <option value="Switch" ${p.category === 'Switch' ? 'selected' : ''}>Switch</option>
                        <option value="Other" ${p.category === 'Other' ? 'selected' : ''}>Other</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Price (₹)*</label>
                    <input type="number" id="prod-price" class="form-control" step="0.01" value="${p.price}" required>
                </div>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
                <div class="form-group">
                    <label>Brand</label>
                    <input type="text" id="prod-brand" class="form-control" value="${p.brand || ''}">
                </div>
                <div class="form-group">
                    <label>Size / Variant</label>
                    <input type="text" id="prod-size" class="form-control" value="${p.size_variant || ''}">
                </div>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
                <div class="form-group">
                    <label>Stock Qty*</label>
                    <input type="number" id="prod-stock" class="form-control" value="${p.stock_qty}" required min="0">
                </div>
                <div class="form-group">
                    <label>Status</label>
                    <select id="prod-active" class="form-control">
                        <option value="true" ${p.is_active ? 'selected' : ''}>Active</option>
                        <option value="false" ${!p.is_active ? 'selected' : ''}>Draft</option>
                    </select>
                </div>
            </div>
            <div class="form-actions" style="margin-top: 1.5rem; display: flex; justify-content: flex-end; gap: 1rem;">
                <button type="button" class="btn btn-outline" onclick="document.querySelector('.modal-overlay').remove()">Cancel</button>
                <button type="submit" class="btn btn-primary">Update Product</button>
            </div>
        </form>
    `);
}

async function saveShopProduct(id = null) {
    const payload = {
        name: document.getElementById('prod-name').value,
        category: document.getElementById('prod-cat').value,
        price: parseFloat(document.getElementById('prod-price').value),
        brand: document.getElementById('prod-brand').value || null,
        size_variant: document.getElementById('prod-size').value || null,
        stock_qty: parseInt(document.getElementById('prod-stock').value, 10),
        is_active: document.getElementById('prod-active').value === 'true'
    };

    try {
        if (id) await api.put(`/shop/products/${id}`, payload);
        else await api.post('/shop/products', payload);

        document.querySelector('.modal-overlay').remove();
        showToast(`Product ${id ? 'updated' : 'added'} successfully`, 'success');
        renderAdminShop();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function deleteShopProduct(id) {
    if (!confirm('Are you sure you want to delete this product?')) return;
    try {
        await api.delete(`/shop/products/${id}`);
        showToast('Product deleted', 'success');
        renderAdminShop();
    } catch (e) {
        showToast(e.message, 'error');
    }
}
