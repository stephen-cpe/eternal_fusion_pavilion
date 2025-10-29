// frontend/src/components/EditCustomerModal.jsx
"use client"

import { useState, useEffect } from "react"
import { adminService } from "../services/api"
import { toast } from "react-toastify"
import { useMutation, useQueryClient } from "@tanstack/react-query"

function EditCustomerModal({ isOpen, onClose, customer }) {
  const [formData, setFormData] = useState({
    name: "",
    email: "",
    phone: "",
    newsletter_signup: false,
  })
  const queryClient = useQueryClient()

  useEffect(() => {
    if (customer) {
      setFormData({
        name: customer.name || "",
        email: customer.email || "",
        phone: customer.phone || "",
        newsletter_signup: customer.newsletter_signup || false,
      })
    }
  }, [customer, isOpen])

  const updateCustomerMutation = useMutation({
    mutationFn: (data) => adminService.updateCustomerDetails(customer.id, data),
    onSuccess: () => {
      toast.success("Customer details updated successfully!")
      queryClient.invalidateQueries(["customers"])
      queryClient.invalidateQueries(["subscribers"]) // In case newsletter status changed
      onClose()
    },
    onError: (error) => {
      toast.error(error.message || "Failed to update customer")
    },
  })

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target
    setFormData((prev) => ({
      ...prev,
      [name]: type === "checkbox" ? checked : value,
    }))
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    updateCustomerMutation.mutate(formData)
  }

  if (!isOpen || !customer) return null

  const isLoading = updateCustomerMutation.isPending

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-60 p-4">
      <div className="bg-card rounded-xl shadow-lg w-full max-w-lg">
        <form onSubmit={handleSubmit}>
          <div className="p-6 border-b border-border">
            <h2 className="text-2xl font-bold">Edit Customer</h2>
            <p className="text-sm text-muted-foreground">Editing profile for {customer.name}</p>
          </div>

          <div className="p-6 grid grid-cols-1 gap-6">
            <div>
              <label className="block text-sm font-medium mb-2">Full Name*</label>
              <input
                type="text"
                name="name"
                value={formData.name}
                onChange={handleChange}
                className="w-full px-3 py-2 border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">Email*</label>
              <input
                type="email"
                name="email"
                value={formData.email}
                onChange={handleChange}
                className="w-full px-3 py-2 border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">Phone (Optional)</label>
              <input
                type="tel"
                name="phone"
                value={formData.phone}
                onChange={handleChange}
                className="w-full px-3 py-2 border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>

            <div className="flex items-center space-x-3">
              <input
                type="checkbox"
                id="newsletter_signup"
                name="newsletter_signup"
                checked={formData.newsletter_signup}
                onChange={handleChange}
                className="h-4 w-4 rounded border-input text-primary focus:ring-primary"
              />
              <label htmlFor="newsletter_signup" className="text-sm font-medium">
                Subscribed to Newsletter
              </label>
            </div>
          </div>

          <div className="p-6 border-t border-border flex justify-end space-x-4">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-input rounded-md hover:bg-muted transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isLoading}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors disabled:opacity-50"
            >
              {isLoading ? "Saving..." : "Save Changes"}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default EditCustomerModal
