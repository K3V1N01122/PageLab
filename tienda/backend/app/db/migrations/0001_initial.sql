-- Esquema inicial del e-commerce.
-- Tokens de dialecto: {{ID}} {{BOOL}} {{TS}} {{JSON}} se sustituyen por el
-- migrador según el motor (SQLite o PostgreSQL). Montos de dinero en centavos
-- (enteros) para evitar errores de redondeo.

-- ---------------------------------------------------------------- roles
CREATE TABLE roles (
    id {{ID}},
    code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    is_staff {{BOOL}} NOT NULL DEFAULT FALSE,
    is_system {{BOOL}} NOT NULL DEFAULT FALSE
);

CREATE TABLE permissions (
    id {{ID}},
    code VARCHAR(80) NOT NULL UNIQUE,
    description VARCHAR(200) NOT NULL
);

CREATE TABLE role_permissions (
    role_id BIGINT NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id BIGINT NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

-- ---------------------------------------------------------------- usuarios
CREATE TABLE users (
    id {{ID}},
    public_id VARCHAR(20) NOT NULL UNIQUE,
    email VARCHAR(254) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(80) NOT NULL,
    last_name VARCHAR(80) NOT NULL,
    phone VARCHAR(30),
    role_id BIGINT NOT NULL REFERENCES roles(id),
    is_active {{BOOL}} NOT NULL DEFAULT TRUE,
    accepted_terms_at {{TS}} NOT NULL,
    email_verified_at {{TS}},
    failed_logins INTEGER NOT NULL DEFAULT 0,
    locked_until {{TS}},
    last_login_at {{TS}},
    created_at {{TS}} NOT NULL,
    updated_at {{TS}} NOT NULL
);
CREATE INDEX idx_users_role ON users(role_id);
CREATE INDEX idx_users_created ON users(created_at);

CREATE TABLE sessions (
    id {{ID}},
    token_hash CHAR(64) NOT NULL UNIQUE,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    persistent {{BOOL}} NOT NULL DEFAULT FALSE,
    ip VARCHAR(64),
    user_agent VARCHAR(300),
    created_at {{TS}} NOT NULL,
    last_seen_at {{TS}} NOT NULL,
    expires_at {{TS}} NOT NULL,
    revoked_at {{TS}}
);
CREATE INDEX idx_sessions_user ON sessions(user_id);
CREATE INDEX idx_sessions_expires ON sessions(expires_at);

CREATE TABLE password_resets (
    id {{ID}},
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash CHAR(64) NOT NULL UNIQUE,
    expires_at {{TS}} NOT NULL,
    used_at {{TS}},
    created_at {{TS}} NOT NULL
);
CREATE INDEX idx_password_resets_user ON password_resets(user_id);

CREATE TABLE addresses (
    id {{ID}},
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    label VARCHAR(50),
    recipient VARCHAR(120) NOT NULL,
    phone VARCHAR(30),
    line1 VARCHAR(200) NOT NULL,
    line2 VARCHAR(200),
    city VARCHAR(100) NOT NULL,
    state VARCHAR(100),
    postal_code VARCHAR(20),
    country VARCHAR(2) NOT NULL DEFAULT 'GT',
    notes VARCHAR(300),
    is_default {{BOOL}} NOT NULL DEFAULT FALSE,
    created_at {{TS}} NOT NULL,
    updated_at {{TS}} NOT NULL
);
CREATE INDEX idx_addresses_user ON addresses(user_id);

-- ---------------------------------------------------------------- catálogo
CREATE TABLE categories (
    id {{ID}},
    parent_id BIGINT REFERENCES categories(id) ON DELETE SET NULL,
    name VARCHAR(120) NOT NULL,
    slug VARCHAR(140) NOT NULL UNIQUE,
    description TEXT,
    image_url VARCHAR(500),
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active {{BOOL}} NOT NULL DEFAULT TRUE,
    seo_title VARCHAR(70),
    seo_description VARCHAR(170),
    created_at {{TS}} NOT NULL,
    updated_at {{TS}} NOT NULL
);
CREATE INDEX idx_categories_parent ON categories(parent_id);

CREATE TABLE products (
    id {{ID}},
    category_id BIGINT REFERENCES categories(id) ON DELETE SET NULL,
    name VARCHAR(200) NOT NULL,
    slug VARCHAR(220) NOT NULL UNIQUE,
    sku VARCHAR(64) NOT NULL UNIQUE,
    short_description VARCHAR(300),
    description TEXT,
    price_cents BIGINT NOT NULL CHECK (price_cents >= 0),
    compare_at_cents BIGINT CHECK (compare_at_cents IS NULL OR compare_at_cents >= 0),
    stock INTEGER NOT NULL DEFAULT 0 CHECK (stock >= 0),
    low_stock_threshold INTEGER NOT NULL DEFAULT 5,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    is_featured {{BOOL}} NOT NULL DEFAULT FALSE,
    is_demo {{BOOL}} NOT NULL DEFAULT FALSE,
    attributes {{JSON}},
    search_text TEXT NOT NULL DEFAULT '',
    seo_title VARCHAR(70),
    seo_description VARCHAR(170),
    sold_count INTEGER NOT NULL DEFAULT 0,
    created_at {{TS}} NOT NULL,
    updated_at {{TS}} NOT NULL
);
CREATE INDEX idx_products_status_created ON products(status, created_at);
CREATE INDEX idx_products_category_status ON products(category_id, status);
CREATE INDEX idx_products_featured ON products(is_featured, status);
CREATE INDEX idx_products_price ON products(status, price_cents);
CREATE INDEX idx_products_sold ON products(status, sold_count);

CREATE TABLE product_images (
    id {{ID}},
    product_id BIGINT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    url VARCHAR(500) NOT NULL,
    alt VARCHAR(200),
    sort_order INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_product_images_product ON product_images(product_id, sort_order);

CREATE TABLE tags (
    id {{ID}},
    name VARCHAR(60) NOT NULL,
    slug VARCHAR(80) NOT NULL UNIQUE
);

CREATE TABLE product_tags (
    product_id BIGINT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    tag_id BIGINT NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (product_id, tag_id)
);
CREATE INDEX idx_product_tags_tag ON product_tags(tag_id);

CREATE TABLE product_related (
    product_id BIGINT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    related_id BIGINT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    PRIMARY KEY (product_id, related_id)
);

CREATE TABLE inventory_movements (
    id {{ID}},
    product_id BIGINT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    delta INTEGER NOT NULL,
    reason VARCHAR(30) NOT NULL,
    ref_type VARCHAR(30),
    ref_id BIGINT,
    user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    created_at {{TS}} NOT NULL
);
CREATE INDEX idx_inventory_product ON inventory_movements(product_id, created_at);

CREATE TABLE favorites (
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product_id BIGINT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    created_at {{TS}} NOT NULL,
    PRIMARY KEY (user_id, product_id)
);

-- ---------------------------------------------------------------- carrito
CREATE TABLE carts (
    id {{ID}},
    user_id BIGINT NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    updated_at {{TS}} NOT NULL
);

CREATE TABLE cart_items (
    id {{ID}},
    cart_id BIGINT NOT NULL REFERENCES carts(id) ON DELETE CASCADE,
    product_id BIGINT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price_cents BIGINT NOT NULL,
    created_at {{TS}} NOT NULL,
    UNIQUE (cart_id, product_id)
);

-- ---------------------------------------------------------------- promociones y cupones
CREATE TABLE promotions (
    id {{ID}},
    name VARCHAR(120) NOT NULL,
    description VARCHAR(300),
    kind VARCHAR(20) NOT NULL,              -- percent | fixed
    value INTEGER NOT NULL,                 -- % o centavos por unidad
    target VARCHAR(20) NOT NULL DEFAULT 'all', -- all | category | product
    target_id BIGINT,
    starts_at {{TS}},
    ends_at {{TS}},
    is_active {{BOOL}} NOT NULL DEFAULT TRUE,
    created_at {{TS}} NOT NULL,
    updated_at {{TS}} NOT NULL
);
CREATE INDEX idx_promotions_active ON promotions(is_active, target, target_id);

CREATE TABLE coupons (
    id {{ID}},
    code VARCHAR(40) NOT NULL UNIQUE,
    description VARCHAR(200),
    kind VARCHAR(20) NOT NULL,              -- fixed | percent | free_shipping | free_product
    value_cents BIGINT NOT NULL DEFAULT 0,
    percent INTEGER NOT NULL DEFAULT 0,
    product_id BIGINT REFERENCES products(id) ON DELETE SET NULL,
    min_subtotal_cents BIGINT NOT NULL DEFAULT 0,
    starts_at {{TS}},
    ends_at {{TS}},
    max_uses INTEGER,
    uses_count INTEGER NOT NULL DEFAULT 0,
    per_user_limit INTEGER NOT NULL DEFAULT 1,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    source VARCHAR(20) NOT NULL DEFAULT 'admin', -- admin | reward
    is_active {{BOOL}} NOT NULL DEFAULT TRUE,
    created_at {{TS}} NOT NULL,
    updated_at {{TS}} NOT NULL
);
CREATE INDEX idx_coupons_user ON coupons(user_id);

-- ---------------------------------------------------------------- fidelización
CREATE TABLE loyalty_cards (
    id {{ID}},
    user_id BIGINT NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    card_number VARCHAR(24) NOT NULL UNIQUE,
    points_balance BIGINT NOT NULL DEFAULT 0 CHECK (points_balance >= 0),
    points_pending BIGINT NOT NULL DEFAULT 0 CHECK (points_pending >= 0),
    lifetime_points BIGINT NOT NULL DEFAULT 0,
    tier VARCHAR(30) NOT NULL DEFAULT 'base',
    created_at {{TS}} NOT NULL,
    updated_at {{TS}} NOT NULL
);

CREATE TABLE rewards (
    id {{ID}},
    name VARCHAR(120) NOT NULL,
    description VARCHAR(300),
    kind VARCHAR(30) NOT NULL,              -- fixed_discount | percent_discount | free_shipping | free_product
    points_cost INTEGER NOT NULL CHECK (points_cost > 0),
    value_cents BIGINT NOT NULL DEFAULT 0,
    percent INTEGER NOT NULL DEFAULT 0,
    product_id BIGINT REFERENCES products(id) ON DELETE SET NULL,
    stock INTEGER,                          -- NULL = ilimitado
    per_user_limit INTEGER,                 -- NULL = ilimitado
    coupon_valid_days INTEGER NOT NULL DEFAULT 30,
    is_active {{BOOL}} NOT NULL DEFAULT TRUE,
    starts_at {{TS}},
    ends_at {{TS}},
    created_at {{TS}} NOT NULL,
    updated_at {{TS}} NOT NULL
);

CREATE TABLE reward_redemptions (
    id {{ID}},
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    reward_id BIGINT NOT NULL REFERENCES rewards(id),
    points INTEGER NOT NULL,
    coupon_id BIGINT REFERENCES coupons(id) ON DELETE SET NULL,
    idempotency_key VARCHAR(80) NOT NULL,
    created_at {{TS}} NOT NULL,
    UNIQUE (user_id, idempotency_key)
);
CREATE INDEX idx_redemptions_reward ON reward_redemptions(reward_id);

-- ---------------------------------------------------------------- pedidos
CREATE TABLE order_statuses (
    code VARCHAR(30) PRIMARY KEY,
    label VARCHAR(60) NOT NULL,
    sort_order INTEGER NOT NULL,
    is_final {{BOOL}} NOT NULL DEFAULT FALSE
);

CREATE TABLE orders (
    id {{ID}},
    order_number VARCHAR(30) NOT NULL UNIQUE,
    user_id BIGINT NOT NULL REFERENCES users(id),
    status VARCHAR(30) NOT NULL REFERENCES order_statuses(code),
    currency VARCHAR(3) NOT NULL,
    subtotal_cents BIGINT NOT NULL,
    discount_cents BIGINT NOT NULL DEFAULT 0,
    points_discount_cents BIGINT NOT NULL DEFAULT 0,
    shipping_cents BIGINT NOT NULL DEFAULT 0,
    total_cents BIGINT NOT NULL CHECK (total_cents >= 0),
    points_used INTEGER NOT NULL DEFAULT 0,
    points_earned INTEGER NOT NULL DEFAULT 0,
    coupon_code VARCHAR(40),
    shipping_method VARCHAR(40) NOT NULL,
    payment_provider VARCHAR(40) NOT NULL,
    payment_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    customer_name VARCHAR(170) NOT NULL,
    customer_email VARCHAR(254) NOT NULL,
    customer_phone VARCHAR(30),
    shipping_address {{JSON}},
    notes VARCHAR(500),
    idempotency_key VARCHAR(80) NOT NULL,
    created_at {{TS}} NOT NULL,
    updated_at {{TS}} NOT NULL,
    UNIQUE (user_id, idempotency_key)
);
CREATE INDEX idx_orders_user_created ON orders(user_id, created_at);
CREATE INDEX idx_orders_status_created ON orders(status, created_at);
CREATE INDEX idx_orders_created ON orders(created_at);

CREATE TABLE order_items (
    id {{ID}},
    order_id BIGINT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id BIGINT REFERENCES products(id) ON DELETE SET NULL,
    product_name VARCHAR(200) NOT NULL,
    sku VARCHAR(64) NOT NULL,
    unit_price_cents BIGINT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    discount_cents BIGINT NOT NULL DEFAULT 0,
    line_total_cents BIGINT NOT NULL
);
CREATE INDEX idx_order_items_order ON order_items(order_id);
CREATE INDEX idx_order_items_product ON order_items(product_id);

CREATE TABLE order_status_history (
    id {{ID}},
    order_id BIGINT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    from_status VARCHAR(30),
    to_status VARCHAR(30) NOT NULL,
    note VARCHAR(300),
    changed_by BIGINT REFERENCES users(id) ON DELETE SET NULL,
    created_at {{TS}} NOT NULL
);
CREATE INDEX idx_order_history_order ON order_status_history(order_id);

CREATE TABLE coupon_usages (
    id {{ID}},
    coupon_id BIGINT NOT NULL REFERENCES coupons(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    order_id BIGINT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    created_at {{TS}} NOT NULL
);
CREATE INDEX idx_coupon_usages ON coupon_usages(coupon_id, user_id);

CREATE TABLE point_movements (
    id {{ID}},
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind VARCHAR(20) NOT NULL,     -- earn | spend | redeem | revoke | refund | adjust
    points INTEGER NOT NULL,       -- positivo suma, negativo resta
    status VARCHAR(20) NOT NULL,   -- pending | posted | cancelled
    description VARCHAR(200) NOT NULL,
    order_id BIGINT REFERENCES orders(id) ON DELETE SET NULL,
    redemption_id BIGINT REFERENCES reward_redemptions(id) ON DELETE SET NULL,
    created_by BIGINT REFERENCES users(id) ON DELETE SET NULL,
    created_at {{TS}} NOT NULL
);
CREATE INDEX idx_points_user_created ON point_movements(user_id, created_at);
CREATE INDEX idx_points_order ON point_movements(order_id);

CREATE TABLE payments (
    id {{ID}},
    order_id BIGINT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    provider VARCHAR(40) NOT NULL,
    status VARCHAR(20) NOT NULL,   -- pending | authorized | paid | failed | refunded
    amount_cents BIGINT NOT NULL,
    currency VARCHAR(3) NOT NULL,
    provider_ref VARCHAR(120),
    details {{JSON}},
    created_at {{TS}} NOT NULL,
    updated_at {{TS}} NOT NULL
);
CREATE INDEX idx_payments_order ON payments(order_id);
CREATE INDEX idx_payments_ref ON payments(provider, provider_ref);

-- ---------------------------------------------------------------- sistema
CREATE TABLE settings (
    key VARCHAR(80) PRIMARY KEY,
    value {{JSON}} NOT NULL,
    updated_at {{TS}} NOT NULL
);

CREATE TABLE rate_limits (
    bucket VARCHAR(200) NOT NULL,
    window_start BIGINT NOT NULL,
    hits INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (bucket, window_start)
);

CREATE TABLE audit_log (
    id {{ID}},
    user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(60) NOT NULL,
    entity VARCHAR(40),
    entity_id BIGINT,
    data {{JSON}},
    ip VARCHAR(64),
    created_at {{TS}} NOT NULL
);
CREATE INDEX idx_audit_created ON audit_log(created_at);
