function uniformApp() {
  const initialProducts = (window.__INITIAL_PRODUCTS__ && window.__INITIAL_PRODUCTS__.length > 0) ? window.__INITIAL_PRODUCTS__ : [];
  const initialCategories = (window.__INITIAL_CATEGORIES__ && window.__INITIAL_CATEGORIES__.length > 0) ? window.__INITIAL_CATEGORIES__ : [];
  
  const defaultSizes = {};
  initialProducts.forEach(p => {
    if (p.sizes && p.sizes.length > 0) {
      defaultSizes[p.id] = p.sizes[0];
    }
  });

  return {
    categories: initialCategories,
    products: initialProducts,
    selectedCategory: 'all',
    searchQuery: '',
    selectedSizes: defaultSizes,
    cart: [],
    loadingCatalog: false,

    // Modales y estados
    openCartDrawer: false,
    openCheckoutModal: false,
    openSuccessModal: false,
    openTrackerModal: false,
    openSizeGuideModal: false,
    openSizeGuide: false,
    openPrivacyModal: false,
    openReturnsPolicyModal: false,
    openExchangeModal: false,
    openPackModal: false,
    openRecommenderModal: false,
    lookbookMode: 'uniforme',
    lookbookModes: ['uniforme', 'infantil', 'chandal'],
    lookbookTimer: null,
    lookbookAutoRotate: true,
    activeHotspot: null,
    submittingOrder: false,
    errorMessage: '',
    toastMessage: '',
    confirmedOrder: null,
    copiedMessage: false,

    // Guía de Uniformidad por Etapa Escolar (Modo Compacto / Móvil)
    activeStage: 'infantil',
    showNoticeDetails: false,
    selectStage(stage) {
      this.activeStage = stage;
    },
    filterByStage(stage) {
      if (stage === 'infantil') {
        this.selectedCategory = 1;
      } else {
        this.selectedCategory = 'all';
      }
      this.searchQuery = '';
      this.scrollToCatalog();
    },

    // Packs Escolares
    activePack: null,
    packForm: {
      globalSize: 'T.8',
      studentName: '',
      itemSizes: {}
    },
    schoolPacks: [
      {
        id: 'infantil',
        name: 'Pack Educación Infantil (3 a 5 años)',
        badge: '🧸 Etapa Infantil',
        badgeColor: 'bg-emerald-100 text-emerald-800 border-emerald-300',
        description: 'Lote completo con babi, chándal infantil, 2 polos manga corta y pantalón corto deportivo.',
        sizes: ['T.2', 'T.3', 'T.4', 'T.5', 'T.6'],
        defaultSize: 'T.4',
        items: [
          { productName: 'Baby - CSB', qty: 1 },
          { productName: 'Chándal - INFANTIL', qty: 1 },
          { productName: 'Polo M/corta - CSB', qty: 2 },
          { productName: 'Pantalón corto de deporte - CSB', qty: 1 }
        ]
      },
      {
        id: 'primaria_nina',
        name: 'Pack Primaria Niña Completo',
        badge: '👧 Primaria Niña',
        badgeColor: 'bg-pink-100 text-pink-800 border-pink-300',
        description: 'Falda de uniforme oficial, jersey de punto, 2 polos m/corta, 1 polo m/larga y chándal con camiseta.',
        sizes: ['T.6', 'T.8', 'T.10', 'T.12'],
        defaultSize: 'T.8',
        items: [
          { productName: 'Falda uniforme - CSB', qty: 1 },
          { productName: 'Jersey uniforme - CSB', qty: 1 },
          { productName: 'Polo M/corta - CSB', qty: 2 },
          { productName: 'Polo M/larga - CSB', qty: 1 },
          { productName: 'Chándal - CSB', qty: 1 },
          { productName: 'Camiseta de deporte - CSB', qty: 1 }
        ]
      },
      {
        id: 'primaria_nino',
        name: 'Pack Primaria Niño Completo',
        badge: '👦 Primaria Niño',
        badgeColor: 'bg-blue-100 text-blue-800 border-blue-300',
        description: 'Pantalón de vestir largo, jersey de punto, 2 polos m/corta, 1 polo m/larga y chándal con camiseta.',
        sizes: ['T.6', 'T.8', 'T.10', 'T.12'],
        defaultSize: 'T.8',
        items: [
          { productName: 'Pantalón vestir largo - CSB', qty: 1 },
          { productName: 'Jersey uniforme - CSB', qty: 1 },
          { productName: 'Polo M/corta - CSB', qty: 2 },
          { productName: 'Polo M/larga - CSB', qty: 1 },
          { productName: 'Chándal - CSB', qty: 1 },
          { productName: 'Camiseta de deporte - CSB', qty: 1 }
        ]
      },
      {
        id: 'deporte',
        name: 'Pack Deporte y E. Física',
        badge: '🏃 Equipación Deportiva',
        badgeColor: 'bg-amber-100 text-amber-800 border-amber-300',
        description: 'Equipación reglamentaria de deporte: chándal completo, sudadera, bermuda y 2 camisetas.',
        sizes: ['T.6', 'T.8', 'T.10', 'T.12', 'T.14', 'T.16', 'T.18'],
        defaultSize: 'T.10',
        items: [
          { productName: 'Chándal - CSB', qty: 1 },
          { productName: 'Pantalón corto de deporte - CSB', qty: 1 },
          { productName: 'Camiseta de deporte - CSB', qty: 2 },
          { productName: 'Sudadera de chándal - CSB', qty: 1 }
        ]
      }
    ],

    // Recomendador de Talla Inteligente
    recommenderHeight: 125,
    recommenderAge: 7,
    recommenderGarmentType: 'superior',

    // Solicitud de cambio
    exchangeItems: {},
    exchangeReason: 'Talla pequeña (necesito una talla más grande)',
    exchangeNotes: '',
    submittingExchange: false,
    exchangeErrorMsg: '',
    exchangeSuccessMsg: '',

    // Formulario con datos de facturación completos
    orderForm: {
      student_name: '',
      student_course: '',
      parent_name: '',
      parent_phone: '',
      parent_email: '',
      parent_nif: '',
      billing_name: '',
      billing_address: '',
      billing_postal_code: '28011',
      billing_city: 'Madrid',
      payment_method: 'Recibo Escolar (cargo domiciliado en cuenta del colegio)',
      notes: '',
      rgpd_accepted: true
    },

    // Tracker
    trackerInput: '',
    trackedOrder: null,
    trackerError: '',
    trackingLoading: false,

    init() {
      const initialLoc = window.__INITIAL_LOCATOR__ || '';
      this.initApp(initialLoc);
    },

    initApp(initialLocator) {
      // Inicializar tallas por defecto si hiciera falta
      this.products.forEach(p => {
        if (p.sizes && p.sizes.length > 0 && !this.selectedSizes[p.id]) {
          this.selectedSizes[p.id] = p.sizes[0];
        }
      });
      if (this.products.length === 0) {
        this.fetchCatalog();
      }
      const urlParams = new URLSearchParams(window.location.search);
      const loc = initialLocator || urlParams.get('locator');
      if (loc) {
        this.trackerInput = loc;
        this.openTrackerModal = true;
        this.trackOrder();
      }
      if (urlParams.get('pack')) {
        const pk = this.schoolPacks.find(p => p.id === urlParams.get('pack'));
        if (pk) this.openConfigurePackModal(pk);
      }
      if (urlParams.get('recommender') === '1') {
        this.openRecommenderModal = true;
      }
      let look = urlParams.get('look');
      if (look === 'primaria') look = 'uniforme';
      if (look === 'patio') look = 'chandal';
      if (look && ['uniforme', 'infantil', 'chandal'].includes(look)) {
        this.lookbookMode = look;
      }
      this.startLookbookRotation();
    },

    startLookbookRotation() {
      if (this.lookbookTimer) clearInterval(this.lookbookTimer);
      this.lookbookTimer = setInterval(() => {
        if (!this.lookbookAutoRotate) return;
        const currentIdx = this.lookbookModes.indexOf(this.lookbookMode);
        const nextIdx = (currentIdx + 1) % this.lookbookModes.length;
        this.lookbookMode = this.lookbookModes[nextIdx];
        this.activeHotspot = null;
      }, 5000);
    },

    setLookbook(mode) {
      this.lookbookMode = mode;
      this.activeHotspot = null;
      this.startLookbookRotation();
    },

    nextLookbook() {
      const currentIdx = this.lookbookModes.indexOf(this.lookbookMode);
      const nextIdx = (currentIdx + 1) % this.lookbookModes.length;
      this.lookbookMode = this.lookbookModes[nextIdx];
      this.activeHotspot = null;
      this.startLookbookRotation();
    },

    async fetchCatalog() {
      try {
        const res = await fetch('/api/catalog');
        const data = await res.json();
        if (data.categories) this.categories = data.categories;
        if (data.products) this.products = data.products;

        // Inicializar tallas por defecto para cada producto
        this.products.forEach(p => {
          if (p.sizes && p.sizes.length > 0 && !this.selectedSizes[p.id]) {
            this.selectedSizes[p.id] = p.sizes[0];
          }
        });
      } catch (e) {
        console.error("Error cargando catálogo", e);
      } finally {
        this.loadingCatalog = false;
      }
    },

    getProductById(id) {
      return this.products.find(p => p.id === id) || null;
    },

    isProductVisible(productId) {
      const p = this.products.find(x => x.id === productId);
      if (!p) return true;
      const matchCategory = this.selectedCategory === 'all' || p.category_id === this.selectedCategory;
      const matchSearch = !this.searchQuery || 
        p.name.toLowerCase().includes(this.searchQuery.toLowerCase()) || 
        (p.description && p.description.toLowerCase().includes(this.searchQuery.toLowerCase())) ||
        (p.code && p.code.toLowerCase().includes(this.searchQuery.toLowerCase()));
      return matchCategory && matchSearch;
    },

    scrollToCatalog() {
      const el = document.getElementById('catalogo');
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    },

    get visibleProductsCount() {
      return this.products.filter(p => this.isProductVisible(p.id)).length;
    },

    get filteredProducts() {
      return this.products.filter(p => {
        const matchCategory = this.selectedCategory === 'all' || p.category_id === this.selectedCategory;
        const matchSearch = !this.searchQuery || 
          p.name.toLowerCase().includes(this.searchQuery.toLowerCase()) || 
          p.description.toLowerCase().includes(this.searchQuery.toLowerCase());
        return matchCategory && matchSearch;
      });
    },

    getCurrentPrice(product) {
      if (!product) return 0;
      const size = this.selectedSizes[product.id] || (product.sizes ? product.sizes[0] : null);
      return this.getPriceForSize(product, size);
    },

    getPriceForSize(product, size) {
      if (!product) return 0;
      if (size && product.size_prices && product.size_prices[size] !== undefined) {
        return product.size_prices[size];
      }
      return product.price;
    },

    addToCart(product, customSize, studentName, customQty) {
      if (!product) return;
      const size = customSize || this.selectedSizes[product.id] || (product.sizes ? product.sizes[0] : 'Única');
      const unitPrice = this.getPriceForSize(product, size);
      const student = (studentName || '').trim();
      const qtyToAdd = parseInt(customQty || 1, 10);

      const existing = this.cart.find(it => it.product_id === product.id && it.size === size && (it.student_name || '') === student);
      if (existing) {
        existing.quantity += qtyToAdd;
      } else {
        this.cart.push({
          product_id: product.id,
          product_name: product.name,
          size: size,
          unit_price: unitPrice,
          quantity: qtyToAdd,
          image_url: product.image_url,
          student_name: student
        });
      }

      this.showToast(`Añadido: ${qtyToAdd}x ${product.name} (${size})` + (student ? ` [${student}]` : '') + ` - ${this.formatMoney(unitPrice * qtyToAdd)}`);
    },

    get upsellSuggestions() {
      const inCartIds = new Set(this.cart.map(it => it.product_id));
      const priorityCodes = ['POL-MC', 'CAM-DEP', 'JER-UNI', 'CHA-COM', 'CAL-LAR', 'BAB-INF'];
      const candidates = this.products.filter(p => !inCartIds.has(p.id));
      candidates.sort((a, b) => {
        const idxA = priorityCodes.indexOf(a.code || '');
        const idxB = priorityCodes.indexOf(b.code || '');
        return (idxA === -1 ? 99 : idxA) - (idxB === -1 ? 99 : idxB);
      });
      return candidates.slice(0, 2);
    },

    get hasMultipleSiblingsInCart() {
      const names = new Set(this.cart.map(it => (it.student_name || '').trim()).filter(Boolean));
      return names.size > 1;
    },

    updateCartQuantity(index, newQty) {
      if (newQty <= 0) {
        this.cart.splice(index, 1);
      } else {
        this.cart[index].quantity = newQty;
      }
    },

    removeCartItem(index) {
      this.cart.splice(index, 1);
    },

    get totalCartCount() {
      return this.cart.reduce((sum, item) => sum + item.quantity, 0);
    },

    get cartTotal() {
      return this.cart.reduce((sum, item) => sum + (item.unit_price * item.quantity), 0);
    },

    showToast(msg) {
      this.toastMessage = msg;
      setTimeout(() => { this.toastMessage = ''; }, 3000);
    },

    async submitOrder() {
      this.submittingOrder = true;
      this.errorMessage = '';

      try {
        if (!this.orderForm.billing_name) {
          this.orderForm.billing_name = this.orderForm.parent_name;
        }
        const payload = {
          ...this.orderForm,
          items: this.cart
        };

        const res = await fetch('/api/orders', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        const result = await res.json();
        if (!res.ok) {
          throw new Error(result.error || 'Error al tramitar la reserva');
        }

        this.confirmedOrder = result;
        this.cart = [];
        this.openCheckoutModal = false;
        this.openSuccessModal = true;

        // Limpiar formulario excepto datos de familia para comodidad
        this.orderForm.student_name = '';
        this.orderForm.student_course = '';
        this.orderForm.notes = '';

      } catch (err) {
        this.errorMessage = err.message;
      } finally {
        this.submittingOrder = false;
      }
    },

    copyLocator(loc) {
      if (!loc) return;
      navigator.clipboard.writeText(loc);
      this.copiedMessage = true;
      setTimeout(() => { this.copiedMessage = false; }, 2500);
    },

    async trackOrder() {
      if (!this.trackerInput) return;
      this.trackingLoading = true;
      this.trackerError = '';
      this.trackedOrder = null;

      try {
        const res = await fetch(`/api/orders/${encodeURIComponent(this.trackerInput.trim().toUpperCase())}`);
        const data = await res.json();
        if (!res.ok) {
          throw new Error(data.error || 'Reserva no encontrada');
        }
        this.trackedOrder = data;
        this.exchangeItems = {};
        if (data.items) {
          data.items.forEach(it => {
            const availSizes = this.getProductSizes(it.product_name);
            const nextSize = availSizes.find(s => s !== it.size) || it.size;
            this.exchangeItems[it.id] = {
              item_id: it.id,
              product_name: it.product_name,
              current_size: it.size,
              unit_price: it.unit_price,
              quantity: it.quantity,
              selected: false,
              action: 'cambiar',
              new_size: nextSize
            };
          });
        }
      } catch (err) {
        this.trackerError = err.message;
      } finally {
        this.trackingLoading = false;
      }
    },

    isStepActive(stepNum, currentStatus) {
      const orderSteps = {
        'Pendiente': 1,
        'En preparación': 2,
        'Listo para recoger': 3,
        'Entregado': 4
      };
      const currentLevel = orderSteps[currentStatus] || 1;
      return currentLevel >= stepNum;
    },

    getCategoryName(catId) {
      const c = this.categories.find(cat => cat.id === catId);
      return c ? c.name : 'Uniformidad';
    },

    getCategoryProductCount(catId) {
      if (catId === 'all') return this.products.length;
      return this.products.filter(p => p.category_id === catId).length;
    },

    formatMoney(val) {
      return Number(val || 0).toLocaleString('es-ES', { style: 'currency', currency: 'EUR' });
    },

    openExchangeModalForOrder() {
      if (!this.trackedOrder || !this.trackedOrder.items) return;
      this.exchangeItems = {};
      this.exchangeErrorMsg = '';
      this.exchangeSuccessMsg = '';
      this.trackedOrder.items.forEach(it => {
        const availSizes = this.getProductSizes(it.product_name);
        const nextSize = availSizes.find(s => s !== it.size) || it.size;
        this.exchangeItems[it.id] = {
          item_id: it.id,
          product_name: it.product_name,
          current_size: it.size,
          unit_price: it.unit_price,
          quantity: it.quantity,
          selected: false,
          action: 'cambiar',
          new_size: nextSize
        };
      });
      this.openExchangeModal = true;
    },

    getProductSizes(productName) {
      const prod = this.products.find(p => p.name.trim().toLowerCase() === (productName || '').trim().toLowerCase());
      if (prod && prod.sizes && prod.sizes.length > 0) {
        return prod.sizes;
      }
      return ['T.2', 'T.3', 'T.4', 'T.5', 'T.6', 'T.8', 'T.10', 'T.12', 'T.14', 'T.16', 'T.18', 'T.20'];
    },

    async submitExchange() {
      this.exchangeErrorMsg = '';
      this.exchangeSuccessMsg = '';
      const selectedList = Object.values(this.exchangeItems).filter(i => i.selected);
      if (selectedList.length === 0) {
        this.exchangeErrorMsg = 'Por favor, marque al menos una prenda para el cambio o devolución.';
        return;
      }

      this.submittingExchange = true;
      try {
        const hasDevolucion = selectedList.some(i => i.action === 'devolver');
        const hasCambio = selectedList.some(i => i.action === 'cambiar');
        const request_type = (hasDevolucion && hasCambio) ? 'mixto' : (hasDevolucion ? 'devolucion' : 'cambio_talla');

        const payload = {
          items: selectedList,
          request_type: request_type,
          reason: this.exchangeReason,
          family_notes: this.exchangeNotes
        };

        const res = await fetch(`/api/orders/${encodeURIComponent(this.trackedOrder.order.locator)}/returns`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        const data = await res.json();
        if (!res.ok) {
          throw new Error(data.error || 'Error registrando la solicitud.');
        }

        this.exchangeSuccessMsg = data.message;
        this.showToast('Solicitud registrada con éxito (' + data.ticket_code + ')');
        setTimeout(() => {
          this.openExchangeModal = false;
          this.trackOrder(); // Refresca los datos en pantalla
        }, 1800);

      } catch (e) {
        this.exchangeErrorMsg = e.message;
      } finally {
        this.submittingExchange = false;
      }
    },

    // ================= METODOS PACKS POR ETAPA ESCOLAR =================
    calculatePackTotal(pack) {
      if (!pack || !pack.items) return 0;
      let total = 0;
      const refSize = pack.defaultSize || 'T.8';
      for (const it of pack.items) {
        const prod = this.findProductByName(it.productName);
        if (prod) {
          total += this.getPriceForSize(prod, refSize) * (it.qty || 1);
        }
      }
      return total;
    },

    findProductByName(name) {
      if (!name) return null;
      const clean = name.toLowerCase().replace(/[^a-z0-9]/g, '');
      return this.products.find(p => {
        const pClean = p.name.toLowerCase().replace(/[^a-z0-9]/g, '');
        return pClean.includes(clean) || clean.includes(pClean);
      }) || null;
    },

    openConfigurePackModal(pack) {
      this.activePack = pack;
      this.packForm.globalSize = pack.defaultSize || 'T.8';
      this.packForm.studentName = '';
      this.packForm.itemSizes = {};
      pack.items.forEach(it => {
        this.packForm.itemSizes[it.productName] = pack.defaultSize || 'T.8';
      });
      this.openPackModal = true;
    },

    openPackById(packId) {
      const pack = this.schoolPacks.find(p => p.id === packId);
      if (pack) {
        this.openConfigurePackModal(pack);
      }
    },

    onGlobalSizeChange(newSize) {
      this.packForm.globalSize = newSize;
      if (this.activePack && this.activePack.items) {
        this.activePack.items.forEach(it => {
          this.packForm.itemSizes[it.productName] = newSize;
        });
      }
    },

    addPackToCart() {
      if (!this.activePack) return;
      let addedCount = 0;
      const student = (this.packForm.studentName || '').trim();

      for (const it of this.activePack.items) {
        const prod = this.findProductByName(it.productName);
        if (prod) {
          const itemSize = this.packForm.itemSizes[it.productName] || this.packForm.globalSize || prod.sizes[0];
          const qty = it.qty || 1;
          for (let i = 0; i < qty; i++) {
            this.addToCart(prod, itemSize, student);
            addedCount++;
          }
        }
      }

      this.openPackModal = false;
      this.showToast(`¡Pack añadido! ${addedCount} prendas reservadas` + (student ? ` para ${student}` : ''));
      this.openCartDrawer = true;
    },

    // ================= METODOS RECOMENDADOR INTELIGENTE DE TALLA =================
    get sizeRecommendation() {
      const h = Number(this.recommenderHeight) || 120;
      const age = Number(this.recommenderAge) || 7;
      const gType = this.recommenderGarmentType || 'superior';

      let size = 'T.8';
      let heightRange = '117 - 128 cm';
      let nextSize = 'T.10';
      let nextRange = '129 - 140 cm';

      if (h < 95) {
        size = 'T.2'; heightRange = '86 - 94 cm'; nextSize = 'T.3'; nextRange = '95 - 100 cm';
      } else if (h <= 104) {
        size = 'T.4'; heightRange = '99 - 104 cm'; nextSize = 'T.6'; nextRange = '105 - 116 cm';
      } else if (h <= 116) {
        size = 'T.6'; heightRange = '105 - 116 cm'; nextSize = 'T.8'; nextRange = '117 - 128 cm';
      } else if (h <= 128) {
        size = 'T.8'; heightRange = '117 - 128 cm'; nextSize = 'T.10'; nextRange = '129 - 140 cm';
      } else if (h <= 140) {
        size = 'T.10'; heightRange = '129 - 140 cm'; nextSize = 'T.12'; nextRange = '141 - 152 cm';
      } else if (h <= 152) {
        size = 'T.12'; heightRange = '141 - 152 cm'; nextSize = 'T.14'; nextRange = '153 - 162 cm';
      } else if (h <= 162) {
        size = 'T.14'; heightRange = '153 - 162 cm'; nextSize = 'T.16'; nextRange = '163 - 170 cm';
      } else if (h <= 170) {
        size = 'T.16'; heightRange = '163 - 170 cm'; nextSize = 'T.18'; nextRange = '171 - 176 cm';
      } else {
        size = 'T.18'; heightRange = '171 - 176 cm'; nextSize = 'T.20'; nextRange = '> 176 cm';
      }

      // Cálculo de margen de crecimiento
      const maxH = parseInt(heightRange.split('-')[1]) || h;
      const diff = maxH - h;
      let advice = '';

      if (diff <= 4) {
        advice = `El alumno/a está en el tramo superior de la ${size}. Para que el uniforme le dure holgado durante todo el curso escolar, recomendamos valorar la ${nextSize} (${nextRange}).`;
      } else if (gType === 'babi' || gType === 'deporte') {
        advice = `Para prendas de abrigo como el babi o la chaqueta de chándal, una talla más (${nextSize}) permite llevar jerséis debajo en invierno con total libertad de movimiento.`;
      } else {
        advice = `La talla ${size} se ajusta perfectamente a la estatura actual de ${h} cm para el curso escolar según el patronaje oficial del Colegio San Buenaventura.`;
      }

      return {
        recommendedSize: size,
        heightRange: heightRange,
        nextSize: nextSize,
        advice: advice
      };
    },

    applyRecommendedSizeToAll() {
      const rec = this.sizeRecommendation.recommendedSize;
      this.products.forEach(p => {
        if (p.sizes && p.sizes.includes(rec)) {
          this.selectedSizes[p.id] = rec;
        }
      });
      this.openRecommenderModal = false;
      this.showToast(`Talla ${rec} seleccionada para las prendas del catálogo.`);
    }

  };
}

// Exponer globalmente tanto en window como en Alpine.data
window.uniformApp = uniformApp;
document.addEventListener('alpine:init', () => {
  if (window.Alpine) {
    window.Alpine.data('uniformApp', uniformApp);
  }
});
