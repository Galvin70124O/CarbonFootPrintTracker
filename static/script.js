// CarbonTrack - JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Theme Toggle
    const themeToggle = document.getElementById('theme-toggle');
    const themeIcon = themeToggle.querySelector('.theme-icon');
    
    // Check for saved theme preference or default to dark
    const savedTheme = localStorage.getItem('theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);
    updateThemeIcon(savedTheme);
    
    themeToggle.addEventListener('click', function() {
        const currentTheme = document.documentElement.getAttribute('data-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        
        document.documentElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
        updateThemeIcon(newTheme);
    });
    
    function updateThemeIcon(theme) {
        themeIcon.textContent = theme === 'dark' ? '🌙' : '☀️';
    }
    
    // Activity Type Dropdown Logic
    const categorySelect = document.getElementById('category');
    const activityTypeSelect = document.getElementById('activity_type');
    const unitSelect = document.getElementById('unit');
    
    // Define activity types for each category
    const activityTypes = {
        electricity: [
            { value: 'fan', label: 'Fan', unit: 'hours' },
            { value: 'ac', label: 'AC', unit: 'hours' },
            { value: 'lights', label: 'Lights', unit: 'hours' },
            { value: 'heater', label: 'Heater', unit: 'hours' },
            { value: 'fridge', label: 'Fridge', unit: 'hours' },
            { value: 'washing_machine', label: 'Washing Machine', unit: 'hours' },
            { value: 'tv', label: 'TV', unit: 'hours' },
            { value: 'computer', label: 'Computer', unit: 'hours' }
        ],
        transport: [
            { value: 'car', label: 'Car', unit: 'km' },
            { value: 'bus', label: 'Bus', unit: 'km' },
            { value: 'train', label: 'Train', unit: 'km' },
            { value: 'flight', label: 'Flight', unit: 'km' },
            { value: 'bike', label: 'Bike', unit: 'km' },
            { value: 'walk', label: 'Walk', unit: 'km' },
            { value: 'taxi', label: 'Taxi', unit: 'km' },
            { value: 'metro', label: 'Metro', unit: 'km' }
        ],
        food: [
            { value: 'rice', label: 'Rice', unit: 'servings' },
            { value: 'chicken', label: 'Chicken', unit: 'servings' },
            { value: 'beef', label: 'Beef', unit: 'servings' },
            { value: 'pork', label: 'Pork', unit: 'servings' },
            { value: 'vegetables', label: 'Vegetables', unit: 'servings' },
            { value: 'fruits', label: 'Fruits', unit: 'servings' },
            { value: 'dairy', label: 'Dairy', unit: 'servings' }
        ],
        waste: [
            { value: 'landfill', label: 'Landfill', unit: 'kg' },
            { value: 'recycled', label: 'Recycled', unit: 'kg' },
            { value: 'composted', label: 'Composted', unit: 'kg' }
        ]
    };
    
    // Update unit options based on category
    const unitOptions = {
        hours: [
            { value: 'hours', label: 'Hours' }
        ],
        km: [
            { value: 'km', label: 'Kilometers' }
        ],
        servings: [
            { value: 'servings', label: 'Servings' },
            { value: 'kg', label: 'Kilograms' }
        ],
        kg: [
            { value: 'kg', label: 'Kilograms' }
        ],
        units: [
            { value: 'units', label: 'Units' }
        ]
    };
    
    if (categorySelect && activityTypeSelect) {
        categorySelect.addEventListener('change', function() {
            const category = this.value;
            
            // Clear current options
            activityTypeSelect.innerHTML = '<option value="">Select Activity</option>';
            activityTypeSelect.disabled = true;
            
            if (category && activityTypes[category]) {
                // Add new options based on category
                activityTypes[category].forEach(function(activity) {
                    const option = document.createElement('option');
                    option.value = activity.value;
                    option.textContent = activity.label;
                    option.dataset.unit = activity.unit;
                    activityTypeSelect.appendChild(option);
                });
                activityTypeSelect.disabled = false;
            }
            
            // Reset unit select
            if (unitSelect) {
                unitSelect.innerHTML = '';
                const defaultUnits = [
                    { value: 'hours', label: 'Hours' },
                    { value: 'km', label: 'Kilometers' },
                    { value: 'servings', label: 'Servings' },
                    { value: 'kg', label: 'Kilograms' },
                    { value: 'units', label: 'Units' }
                ];
                defaultUnits.forEach(function(unit) {
                    const option = document.createElement('option');
                    option.value = unit.value;
                    option.textContent = unit.label;
                    unitSelect.appendChild(option);
                });
            }
        });
        
        // Auto-update unit when activity type is selected
        activityTypeSelect.addEventListener('change', function() {
            const selectedOption = this.options[this.selectedIndex];
            const defaultUnit = selectedOption.dataset.unit;
            
            if (defaultUnit && unitSelect) {
                // Update unit dropdown with relevant options
                unitSelect.innerHTML = '';
                const options = unitOptions[defaultUnit] || unitOptions.units;
                options.forEach(function(unit) {
                    const option = document.createElement('option');
                    option.value = unit.value;
                    option.textContent = unit.label;
                    unitSelect.appendChild(option);
                });
            }
        });
    }
    
    // Set default date to today
    const manualDateInput = document.getElementById('manual_date');
    if (manualDateInput) {
        const today = new Date().toISOString().split('T')[0];
        manualDateInput.max = today;
    }
    
    // Form validation
    const activityForm = document.querySelector('.activity-form');
    if (activityForm) {
        activityForm.addEventListener('submit', function(e) {
            const category = document.getElementById('category').value;
            const activityType = document.getElementById('activity_type').value;
            const amount = parseFloat(document.getElementById('amount').value);
            
            if (!category || !activityType || !amount || amount <= 0) {
                e.preventDefault();
                alert('Please fill in all fields correctly.');
            }
        });
    }
});