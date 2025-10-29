import React, { useState } from 'react';
import { newsletterService } from '../services/api';

function NewsletterSignup() {
  const [email, setEmail] = useState('');
  const [name, setName] = useState('');
  const [message, setMessage] = useState('');
  const [messageType, setMessageType] = useState(''); // 'success' or 'error'
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    setIsSubmitting(true);
    try {
      await newsletterService.subscribe(email, name);
      setMessage('Thank you for subscribing to our newsletter! You\'ll receive updates about our special events and seasonal menu.');
      setMessageType('success');
      // Reset form
      setEmail('');
      setName('');
      // Clear message after 2 seconds
      setTimeout(() => {
        setMessage('');
        setMessageType('');
      }, 2000);
    } catch (error) {
      setMessage(error.message || 'Sorry, there was an error processing your subscription. Please try again.');
      setMessageType('error');
      
      // Clear message after 2 seconds
      setTimeout(() => {
        setMessage('');
        setMessageType('');
      }, 2000);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <section className="py-16 px-4 bg-muted">
      {/* Centered container with flexbox */}
      <div className="flex justify-center">
        <div className="w-full max-w-3xl">
          <div className="bg-card p-8 rounded-lg shadow-sm border border-border">
            <div className="text-center mb-8">
              <h2 className="text-3xl font-bold text-deep-blue mb-4">Join Our Family</h2>
              <p className="text-muted-foreground">
                Inspired by our founders' stories? Become part of the Eternal Fusion family—sign up for our newsletter for exclusive recipes, events, and behind-the-scenes insights from Chefs Michiko, Giovanni, and Doña Esperanza.
              </p>
            </div>
            
            <form onSubmit={handleSubmit} className="max-w-md mx-auto">
              <div className="grid gap-4">
                <div className="space-y-2">
                  <label htmlFor="name" className="block text-sm font-medium text-deep-blue">
                    Your Name (Optional)
                  </label>
                  <input
                    id="name"
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className="w-full px-3 py-2 border border-input rounded-md focus:outline-none focus:ring-1 focus:ring-ring"
                    placeholder="Your name"
                  />
                </div>
                
                <div className="space-y-2">
                  <label htmlFor="email" className="block text-sm font-medium text-deep-blue">
                    Email Address
                  </label>
                  <input
                    id="email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    className="w-full px-3 py-2 border border-input rounded-md focus:outline-none focus:ring-1 focus:ring-ring"
                    placeholder="you@example.com"
                  />
                </div>
                
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className={"btn w-full"}
                >
                  {isSubmitting ? 'Subscribing...' : 'Subscribe'}
                </button>
              </div>
              
              {message && (
                <div className={`mt-4 p-4 rounded-lg text-sm ${
                  messageType === 'success' 
                    ? 'bg-green-50 text-green-800 border border-green-200' 
                    : 'bg-red-50 text-red-800 border border-red-200'
                }`}>
                  {message}
                </div>
              )}
            </form>
          </div>
        </div>
      </div>
    </section>
  );
}

export default NewsletterSignup;