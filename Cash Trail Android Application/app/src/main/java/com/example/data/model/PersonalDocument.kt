package com.example.data.model

import com.google.firebase.Timestamp
import com.google.firebase.firestore.DocumentId
import com.google.firebase.firestore.IgnoreExtraProperties
import com.google.firebase.firestore.ServerTimestamp
import java.util.UUID

enum class DocumentCategory(val displayName: String, val subtitle: String) {
    IDENTITY("Identity & Proofs", "Aadhaar, PAN, Passport, Driving License, Voter ID"),
    FINANCIAL("Banking & Finance", "Passbook, Cheque Leaf, Demat, Statements"),
    INSURANCE("Insurance & Health", "Health Policy, Term Life, Vehicle Insurance"),
    TAX_LEGAL("Tax & Legal", "ITR, Form 16, Property Deeds, Rental Agreement"),
    VEHICLE("Vehicle & Transport", "RC Book, PUC Certificate, Driving Permit"),
    BILLS("Bills & Statements", "Electricity, Gas, Broadband, Purchase Bills"),
    OTHER("Other Documents", "Certificates, Warranties, General")
}

@IgnoreExtraProperties
data class PersonalDocument(
    @DocumentId val id: String = UUID.randomUUID().toString(),
    val userId: String = "",
    val name: String = "",
    val category: String = DocumentCategory.IDENTITY.name,
    val documentNumber: String = "",
    val issuer: String = "",
    val expiryDate: String = "",
    val issueDate: String = "",
    val notes: String = "",
    val fileUri: String = "",
    val fileName: String = "",
    val colorHex: String = "#1E88E5",
    val isFavorite: Boolean = false,
    @ServerTimestamp val createdAt: Timestamp? = null,
    @ServerTimestamp val updatedAt: Timestamp? = null
)
