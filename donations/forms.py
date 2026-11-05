from django import forms
from .models import DonationCampaign, Donation, Payout, DonationCampaignItem


class DonationCampaignForm(forms.ModelForm):
    needed_items = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Enter one item per line, e.g. Torch | 5'
        }),
        required=True,
        help_text='List campaign items: one item per line. Example: Torch | 5'
    )

    class Meta:
        model = DonationCampaign
        fields = ['title', 'description', 'ends_at', 'needed_items']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Campaign title'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Describe the equipment your campaign needs...'
            }),
            'ends_at': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
        }

    def clean_needed_items(self):
        value = self.cleaned_data['needed_items']
        lines = [line.strip() for line in value.splitlines() if line.strip()]
        items = []
        for line in lines:
            parts = [part.strip() for part in line.split('|')]
            if (
                len(parts) != 2
                or not parts[0]
                or not parts[1].isdigit()
                or not 1 <= int(parts[1]) <= 100000
            ):
                raise forms.ValidationError(
                    'Each line must use the format: Item Name | Quantity, '
                    'with a quantity between 1 and 100000.'
                )
            items.append((parts[0], int(parts[1])))
        return items

    def save(self, commit=True):
        needed_items = self.cleaned_data.pop('needed_items', [])
        campaign = super().save(commit=commit)
        if commit:
            self.save_items(campaign, needed_items)
        else:
            self._pending_items = needed_items
        return campaign

    def save_items(self, campaign, items=None):
        if items is None:
            items = getattr(self, '_pending_items', [])
        for name, quantity in items:
            DonationCampaignItem.objects.create(
                campaign=campaign,
                name=name,
                quantity_needed=quantity,
            )
        return campaign


class DonationForm(forms.ModelForm):
    quantity = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Quantity',
            'min': '1',
        }),
    )

    campaign_item = forms.ModelChoiceField(
        queryset=DonationCampaignItem.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Item to Donate',
        required=False,
    )

    class Meta:
        model = Donation
        fields = ['campaign_item', 'equipment_name', 'quantity', 'condition', 'pickup_address', 'phone_number', 'message']
        widgets = {
            'equipment_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Equipment Name'
            }),
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Quantity',
                'min': '1'
            }),
            'condition': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Condition (New, Good, Used)'
            }),
            'pickup_address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Pickup address for the donation'
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Phone number for pickup'
            }),
            'message': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Optional message'
            }),
        }

    def __init__(self, *args, campaign=None, **kwargs):
        super().__init__(*args, **kwargs)
        if campaign is not None:
            self.fields['campaign_item'].queryset = campaign.items.all()
            self.fields['campaign_item'].label_from_instance = lambda obj: f'{obj.name} ({obj.quantity_needed - obj.quantity_received} needed)'
            self.fields['campaign_item'].required = True
            self.fields['equipment_name'].required = False
        else:
            self.fields.pop('campaign_item', None)

    def clean(self):
        cleaned_data = super().clean()
        campaign_item = cleaned_data.get('campaign_item')
        quantity = cleaned_data.get('quantity')
        if campaign_item:
            cleaned_data['equipment_name'] = campaign_item.name
            remaining = campaign_item.quantity_needed - campaign_item.quantity_received
            if quantity and quantity > remaining:
                self.add_error('quantity', f'Only {remaining} of this item are still needed.')
        return cleaned_data


class PayoutRequestForm(forms.ModelForm):
    amount = forms.DecimalField(
        min_value=100,
        decimal_places=2,
        max_digits=10,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Amount to withdraw (R)',
            'min': '100',
            'step': '0.01',
        }),
    )

    class Meta:
        model = Payout
        fields = ['amount', 'bank_name', 'account_number', 'account_holder']
        widgets = {
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Amount to withdraw (R)',
                'min': '100',
                'step': '0.01'
            }),
            'bank_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., ABSA, FNB, Standard Bank'
            }),
            'account_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Your account number'
            }),
            'account_holder': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Account holder name'
            }),
        }


class PayoutProcessForm(forms.ModelForm):
    class Meta:
        model = Payout
        fields = ['status']
        widgets = {
            'status': forms.Select(attrs={
                'class': 'form-select'
            }),
        }
